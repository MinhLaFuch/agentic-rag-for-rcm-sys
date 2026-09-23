from package.agent.config.loader import load_config
from package.agent.llm.base import LLMMessage
from package.agent.llm.factory import build_llm_provider


def main() -> None:
    config = load_config("agent")
    provider = build_llm_provider(config)
    print(f"Provider: {provider.provider_name}")
    print(f"Health check: {provider.health_check()}")

    response = provider.complete(
        [
            LLMMessage(role="system", content="You are a recommendation reranker."),
            LLMMessage(role="user", content="Rerank these 3 laptops by battery life."),
        ],
        response_format_json=True,
    )
    print("--- Response ---")
    print(f"text: {response.text}")
    print(f"provider_name: {response.provider_name}")
    print(f"model_name: {response.model_name}")
    print(f"latency_seconds: {response.latency_seconds}")


if __name__ == "__main__":
    main()
