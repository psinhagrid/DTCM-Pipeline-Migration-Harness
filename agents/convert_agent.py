import asyncio

from event_queue import push

NAME = "convert_agent"


async def _s(message: str, done: bool = False) -> None:
    await push(type="status", agent=NAME, message=message, done=done)


async def run(metadata: dict) -> dict:
    tables: int = metadata.get("tables", 4)
    udfs: int   = metadata.get("udfs", 0)

    await _s("Starting HiveQL → Spark SQL translation...")
    await asyncio.sleep(1.0)

    for i in range(1, tables + 1):
        await _s(f"Translating table_{i}.hql → Spark SQL")
        await asyncio.sleep(0.7)

    if udfs:
        await _s(f"Rewriting {udfs} UDF(s) for Spark compatibility")
        await asyncio.sleep(1.0)

    await _s("Generating MWAA DAG...")
    await asyncio.sleep(1.2)

    await _s("✓ DAG generated: migration_dag.py")
    await asyncio.sleep(0.5)

    await _s("Writing artifacts to S3...")
    await asyncio.sleep(0.8)

    await _s("✓ Artifacts written to s3://dtcm-pipeline/output/", done=True)

    return {"dag": "migration_dag.py", "tables_converted": tables}
