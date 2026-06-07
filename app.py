import os
import asyncio
import shlex
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

# Load environment variables from .env if it exists
load_dotenv()


def get_gemini_llm(api_key: str) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", google_api_key=api_key, temperature=0.7
    )


def get_openrouter_llm(api_key: str, model_name: str) -> ChatOpenAI:
    return ChatOpenAI(
        model=model_name,
        openai_api_key=api_key,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0.7,
        max_tokens=512,
        default_headers={
            "HTTP-Referer": "https://github.com/langchain-ai/langchain",
            "X-Title": "Langchain Simple CLI",
        },
    )


async def run_chat_loop(chain_or_agent, is_agent=False):
    print("\nInitialization successful!")
    print("-> Type your prompt below to chat.")
    print("-> Type 'menu' to switch provider, model, or keys.")
    print("-> Type 'exit' or 'quit' to close the application.")
    print("-" * 50)

    exit_app = False
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            if user_input.lower() == "menu":
                print("\nReturning to model selection menu...")
                break
            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye!")
                exit_app = True
                break

            print("AI is thinking...")

            if is_agent:
                # Agent expects messages dictionary
                response_stream = await chain_or_agent.ainvoke(
                    {"messages": [("user", user_input)]}
                )
                response = response_stream["messages"][-1].content
            else:
                # Simple chain expects user_input
                response = await chain_or_agent.ainvoke({"user_input": user_input})

            # Format list-based content (e.g. content blocks) to a string
            if isinstance(response, list):
                response = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in response
                )

            print(f"\nResponse:\n{response}")
            print("-" * 50)

        except Exception as e:
            print(f"\nAn error occurred: {e}")
            print("-" * 50)

    return exit_app


async def handle_mcp_agent():
    try:
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp.client.session import ClientSession
        from langchain_mcp_adapters.tools import load_mcp_tools
        from langgraph.prebuilt import create_react_agent
    except ImportError:
        print(
            "Error: MCP dependencies missing. Make sure you installed mcp, langchain-mcp-adapters, and langgraph."
        )
        return False

    # Ask for MCP command
    print(
        "\nEnter the command to run your MCP server (e.g., npx -y @modelcontextprotocol/server-brave-search)"
    )
    print("If using npx on Windows, consider using npx.cmd")
    mcp_command_str = input("MCP Command: ").strip()
    if not mcp_command_str:
        print("Command is required.")
        return False

    cmd_parts = shlex.split(mcp_command_str)
    command = cmd_parts[0]
    args = cmd_parts[1:]

    # Provider for agent
    print("\nWhich LLM should the Agent use?")
    print("1. Google Gemini (default model)")
    print("2. OpenRouter (requires a model supporting tool calling)")
    agent_llm_choice = input("Choice (1 or 2): ").strip()

    llm = None
    if agent_llm_choice == "1":
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            api_key = input("Enter Gemini API Key: ").strip()
        if not api_key:
            return False
        llm = get_gemini_llm(api_key)
    elif agent_llm_choice == "2":
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            api_key = input("Enter OpenRouter API Key: ").strip()
        if not api_key:
            return False
        # Let's use a default model that supports tool calling
        model_name = input(
            "Enter model ID [default: google/gemini-2.5-flash]: "
        ).strip()
        if not model_name:
            model_name = "google/gemini-2.5-flash"
        llm = get_openrouter_llm(api_key, model_name)
    else:
        print("Invalid choice.")
        return False

    server_params = StdioServerParameters(command=command, args=args)

    print("\nConnecting to MCP Server and loading tools...")
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await load_mcp_tools(session)

                print(f"Loaded {len(tools)} tools from MCP server.")
                agent = create_react_agent(
                    llm,
                    tools,
                    prompt="You are a helpful assistant. Use your tools to answer questions, especially about LangChain and LangGraph.",
                )

                exit_app = await run_chat_loop(agent, is_agent=True)
                return exit_app
    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"Failed to connect to MCP server: {e}")
        return False


async def main():
    print("=========================================")
    print("   Simple Dynamic LangChain CLI Client   ")
    print("=========================================\n")

    while True:
        print("\nSelect LLM Provider or Mode:")
        print("1. Google Gemini (Simple Chat)")
        print("2. OpenRouter (Simple Chat)")
        print("3. Connect MCP Server (Agent Mode with LangGraph)")
        print("4. Exit Application")

        choice = input("\nEnter choice (1-4): ").strip()

        if choice in ["4", "exit", "quit"]:
            print("Goodbye!")
            break

        if choice == "3":
            exit_app = await handle_mcp_agent()
            if exit_app:
                break
            continue

        llm = None

        if choice == "1":
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                api_key = input("Enter your Gemini API Key: ").strip()
            if not api_key:
                print("Error: Gemini API Key is required. Returning to menu.")
                continue

            print("\nInitializing Google Gemini (gemini-2.5-flash)...")
            llm = get_gemini_llm(api_key)

        elif choice == "2":
            api_key = os.environ.get("OPENROUTER_API_KEY")
            if not api_key:
                api_key = input("Enter your OpenRouter API Key: ").strip()
            if not api_key:
                print("Error: OpenRouter API Key is required. Returning to menu.")
                continue

            free_models = {
                "1": "google/gemini-2.5-flash",
                "2": "meta-llama/llama-3.3-70b-instruct:free",
                "3": "deepseek/deepseek-r1:free",
                "4": "qwen/qwen-2.5-coder-32b-instruct:free",
                "5": "openrouter/free",
            }

            print("\nAvailable Free Models on OpenRouter:")
            for key, name in free_models.items():
                print(f"  {key}. {name}")

            model_choice = input("\nSelect a model number (1-5) [default: 1]: ").strip()

            if not model_choice:
                model_name = free_models["1"]
            elif model_choice in free_models:
                model_name = free_models[model_choice]
            else:
                model_name = model_choice

            print(f"\nInitializing OpenRouter ({model_name})...")
            llm = get_openrouter_llm(api_key, model_name)

        else:
            print("Invalid selection.")
            continue

        # Standard simple chat chain
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "You are a helpful and concise AI assistant."),
                ("user", "{user_input}"),
            ]
        )
        output_parser = StrOutputParser()
        chain = prompt | llm | output_parser

        exit_app = await run_chat_loop(chain, is_agent=False)
        if exit_app:
            break


if __name__ == "__main__":
    asyncio.run(main())
