import logging

logging.basicConfig(
    format = '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s',
    level = logging.DEBUG,
)

import boto3
import psycopg2
from ..settings import settings
from .lcs import load_measurements_db, load_metadata_db, load_versions_db
from .fetch import load_db
import math

from datetime import datetime, timezone

s3c = boto3.client("s3")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG);

def handler(event, context):
    logger.debug(event)
    records = event.get("Records")
    if records is not None:
        try:
            with psycopg2.connect(settings.DATABASE_WRITE_URL) as connection:
                with connection.cursor() as cursor:
                    connection.set_session(autocommit=True)
                    for record in records:
                        bucket = record["s3"]["bucket"]["name"]
                        key = record["s3"]["object"]["key"]

                        lov2 = s3c.list_objects_v2(
                            Bucket=bucket, Prefix=key, MaxKeys=1
                        )
                        try:
                            last_modified = lov2["Contents"][0]["LastModified"]
                        except KeyError:
                            logger.warning("could not get last modified time from obj")
                        last_modified = datetime.now().replace(
                            tzinfo=timezone.utc
                        )

                        cursor.execute(
                            """
                            INSERT INTO fetchlogs (key, last_modified)
                            VALUES(%s, %s)
                            ON CONFLICT (key) DO UPDATE
                            SET last_modified=EXCLUDED.last_modified,
                            completed_datetime=NULL RETURNING *;
                            """,
                            (key, last_modified,),
                        )
                        row = cursor.fetchone()
                        connection.commit()
                        logger.debug(f"{row}")
        except Exception as e:
            logger.warning(f"Exception: {e}")
    elif event.get("source") and event["source"] == "aws.events":
        logger.info("aws.event")
        cronhandler(event, context)


def cronhandler(event, context):
    logger.info("starting cron job")
    logger.debug(event)
    with psycopg2.connect(settings.DATABASE_WRITE_URL) as connection:
        connection.set_session(autocommit=True)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*) FROM fetchlogs WHERE completed_datetime is null and key ~*'stations';
                """,
            )
            metadata = cursor.fetchone()
            cursor.execute(
                """
                SELECT count(*) FROM fetchlogs WHERE completed_datetime is null and key ~*'measures';
                """,
            )
            pipeline = cursor.fetchone()
            cursor.execute(
                """
                SELECT count(*) FROM fetchlogs WHERE completed_datetime is null and key ~*'versions';
                """,
            )
            versions = cursor.fetchone()
            cursor.execute(
                """
                SELECT count(*) FROM fetchlogs WHERE completed_datetime is null and key ~*'realtime';
                """,
            )
            realtime = cursor.fetchone()
            for notice in connection.notices:
                logger.info(notice)

    logger.info(f"Processing {metadata[0]} metadata, {realtime[0]} openaq, {pipeline[0]} pipeline records")
    if metadata is not None:
        val = int(metadata[0])
        cnt = 0
        while cnt < val + 10:
            load_metadata_db(10)
            cnt += 10
            logger.debug(f"loaded {cnt+10} of {val} metadata/station records")

    if realtime is not None:
        val = int(realtime[0])
        if val>400:
            val=400
        cnt = 0
        while cnt < val + 25:
            load_db(25)
            cnt += 25
            logger.debug(f"loaded {cnt+25} of {val} fetch/realtime records")

    if pipeline is not None:
        val = int(pipeline[0])
        if val>400:
            val=400
        cnt = 0
        while cnt < val + 25:
            load_measurements_db(25)
            cnt += 25
            logger.debug(f"loaded {cnt+25} of {val} measurement records")

    if versions is not None:
        val = int(versions[0])
        if val>400:
            val=400
        cnt = 0
        while cnt < val + 25:
            load_versions_db(25)
            cnt += 25
            logger.debug(f"loaded {cnt+25} of {val} versions records")

    logger.info("ending cron job")
