
import asyncio
import structlog
from src.database import get_db_client

logger = structlog.get_logger()

async def run_maintenance_tasks():
    """Background task to clean up stale jobs and claims"""
    db = get_db_client()

    while True:
        try:
            await asyncio.sleep(60)  # Run every minute

            # Release stale claims (claimed but not started in 5 minutes)
            # Use try-except separately so one failure doesn't block the other
            try:
                released = await db.release_stale_claims(stale_minutes=5)
                if released > 0:
                    logger.info("stale_claims_released", count=released)
            except Exception as e:
                logger.error("stale_claims_release_error", error=str(e))

            # Mark stale executions as failed (executing > 2x timeout)
            try:
                failed = await db.mark_stale_executions_failed(timeout_multiplier=2.0)
                if failed > 0:
                    logger.warning("stale_executions_marked_failed", count=failed)
            except Exception as e:
                logger.error("stale_executions_check_error", error=str(e))

        except asyncio.CancelledError:
            logger.info("maintenance_tasks_stopped")
            raise
        except Exception as e:
            logger.error("maintenance_task_error", error=str(e))
            # Sleep a bit before retrying to avoid spamming logs if DB is down
            await asyncio.sleep(60)
