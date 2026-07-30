from langsmith import Client
import config


class LangSmithClient:
    """Wraps langsmith.Client() for run logging. Only layer that imports langsmith."""

    def __init__(self):
        self._client = Client(api_key=config.LANGSMITH_API_KEY)

    def create_run(
        self,
        run_id,
        name: str,
        run_type: str,
        inputs: dict,
        outputs: dict,
        metadata: dict,
        project_name: str,
        start_time,
        end_time,
    ) -> None:
        self._client.create_run(
            id=run_id,
            name=name,
            run_type=run_type,
            inputs=inputs,
            outputs=outputs,
            extra={"metadata": metadata},
            project_name=project_name,
            start_time=start_time,
            end_time=end_time,
        )
