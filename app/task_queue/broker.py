from taskiq import SimpleRetryMiddleware
import taskiq_fastapi
from taskiq_aio_pika import AioPikaBroker
from taskiq import TaskiqMessage, TaskiqMiddleware, TaskiqResult

class CatchErrorMiddleware(TaskiqMiddleware):
    async def on_error(
        self,
        message: TaskiqMessage,
        result: TaskiqResult,
        exception: BaseException,
    ) -> None:
        """
        Обработчик ошибок в задачах.
        Логирует ошибку, можно сохранить в БД.
        """
        print("***********************************************")
        print(f"Error in task: {message.task_name}")
        print(f"Labels: {message.labels}")
        error = str(exception)
        print(f"Error: {error}")
        print("***********************************************")

# создаем брокер с middleware'ами
broker = AioPikaBroker(
    url="amqp://guest:guest@localhost:5672//",
).with_middlewares(
    SimpleRetryMiddleware(default_retry_count=3),  # retry механизм
    CatchErrorMiddleware(),
)

# инициализируем TaskIQ с FastAPI
taskiq_fastapi.init(broker, "main:main_app")

__all__ = ("broker",)