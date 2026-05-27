export type Lang = "python" | "hive";

export const TOKEN_COLORS: Record<string, string> = {
  keyword:   "text-blue-400",
  string:    "text-emerald-300",
  comment:   "text-slate-400",
  number:    "text-orange-400",
  decorator: "text-yellow-300",
  builtin:   "text-cyan-400",
  plain:     "text-slate-200",
};

const PY_KW   = new Set(["False","None","True","and","as","assert","async","await","break","class","continue","def","del","elif","else","except","finally","for","from","global","if","import","in","is","lambda","nonlocal","not","or","pass","raise","return","try","while","with","yield"]);
const PY_BLTN = new Set(["abs","all","any","bool","bytes","callable","chr","dict","enumerate","eval","exec","filter","float","format","frozenset","getattr","globals","hasattr","hash","hex","id","input","int","isinstance","issubclass","iter","len","list","locals","map","max","min","next","object","oct","open","ord","pow","print","property","range","repr","reversed","round","set","setattr","slice","sorted","staticmethod","str","sum","super","tuple","type","vars","zip","self","cls"]);
const HQL_KW  = new Set(["SELECT","FROM","WHERE","INSERT","INTO","VALUES","CREATE","TABLE","DROP","ALTER","UPDATE","DELETE","JOIN","LEFT","RIGHT","INNER","OUTER","FULL","CROSS","ON","GROUP","ORDER","BY","HAVING","DISTINCT","AS","UNION","ALL","LIMIT","PARTITION","CLUSTER","SORT","OVERWRITE","IF","EXISTS","NOT","AND","OR","IN","LIKE","BETWEEN","IS","NULL","CASE","WHEN","THEN","ELSE","END","WITH","SET","USE","SHOW","DESCRIBE","EXPLAIN","LATERAL","VIEW","EXPLODE","LOAD","DATA","LOCAL","INPATH","EXTERNAL","LOCATION","ROW","FORMAT","DELIMITED","FIELDS","TERMINATED","STORED","TEXTFILE","ORC","PARQUET","SEQUENCEFILE","AVRO"]);
const HQL_FN  = new Set(["COUNT","SUM","AVG","MAX","MIN","COALESCE","NVL","CONCAT","SUBSTR","SUBSTRING","LENGTH","UPPER","LOWER","TRIM","CAST","TO_DATE","DATEDIFF","YEAR","MONTH","DAY","NOW","CURRENT_DATE","CURRENT_TIMESTAMP","COLLECT_LIST","COLLECT_SET","PERCENTILE","RANK","ROW_NUMBER","DENSE_RANK","LEAD","LAG","FIRST_VALUE","LAST_VALUE","NTILE","CUME_DIST","PERCENT_RANK","FLOOR","CEIL","ROUND","ABS","MOD","POWER","SQRT","LOG","EXP","UNIX_TIMESTAMP","FROM_UNIXTIME","DATE_FORMAT","REGEXP_REPLACE","REGEXP_EXTRACT","SPLIT","GET_JSON_OBJECT"]);

export function tokenizeLine(line: string, lang: Lang): Array<{ text: string; kind: string }> {
  if (!line) return [{ text: "", kind: "plain" }];
  const tokens: Array<{ text: string; kind: string }> = [];
  let i = 0;
  while (i < line.length) {
    const rest = line.slice(i);
    const ch = rest[0];
    if (lang === "python" && ch === "#") { tokens.push({ text: rest, kind: "comment" }); break; }
    if (lang === "hive"   && rest.startsWith("--")) { tokens.push({ text: rest, kind: "comment" }); break; }
    if (lang === "python" && ch === "@") {
      const m = rest.match(/^@[\w.]+/);
      if (m) { tokens.push({ text: m[0], kind: "decorator" }); i += m[0].length; continue; }
    }
    if (ch === '"' || ch === "'") {
      let end = 1;
      while (end < rest.length) {
        if (lang === "python" && rest[end] === "\\") { end += 2; continue; }
        if (rest[end] === ch) { end++; break; }
        end++;
      }
      tokens.push({ text: rest.slice(0, end), kind: "string" }); i += end; continue;
    }
    if (/[a-zA-Z_]/.test(ch)) {
      const m = rest.match(/^[a-zA-Z_]\w*/);
      if (m) {
        const w = m[0];
        let kind = "plain";
        if (lang === "python") { if (PY_KW.has(w)) kind = "keyword"; else if (PY_BLTN.has(w)) kind = "builtin"; }
        else { if (HQL_KW.has(w.toUpperCase())) kind = "keyword"; else if (HQL_FN.has(w.toUpperCase())) kind = "builtin"; }
        tokens.push({ text: w, kind }); i += w.length; continue;
      }
    }
    if (/\d/.test(ch)) {
      const m = rest.match(/^\d+\.?\d*/);
      if (m) { tokens.push({ text: m[0], kind: "number" }); i += m[0].length; continue; }
    }
    tokens.push({ text: ch, kind: "plain" }); i++;
  }
  return tokens;
}
