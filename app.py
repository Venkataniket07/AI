import os
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

# Load environment variables from .env if it exists
load_dotenv()

def get_gemini_llm(api_key: str) -> ChatGoogleGenerativeAI:
    # Initialize Google Gemini using langchain-google-genai
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key,
        temperature=0.7
    )

def get_openrouter_llm(api_key: str, model_name: str) -> ChatOpenAI:
    # Initialize OpenRouter using langchain-openai with custom base url
    return ChatOpenAI(
        model=model_name,
        openai_api_key=api_key,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0.7,
        max_tokens=512,  # Limit response token budget to satisfy credit checks
        # OpenRouter requires headers for identification sometimes
        default_headers={
            "HTTP-Referer": "https://github.com/langchain-ai/langchain",
            "X-Title": "Langchain Simple CLI"
        }
    )

def main():
    print("=========================================")
    print("   Simple Dynamic LangChain CLI Client   ")
    print("=========================================\n")

    while True:
        # 1. Choose provider
        print("\nSelect LLM Provider:")
        print("1. Google Gemini (default model: gemini-2.5-flash)")
        print("2. OpenRouter (e.g. free/flash models)")
        print("3. Exit Application")
        
        choice = input("\nEnter choice (1, 2 or 3): ").strip()
        
        if choice in ["3", "exit", "quit"]:
            print("Goodbye!")
            break
            
        llm = None
        
        if choice == "1":
            # Google Gemini setup
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                api_key = input("Enter your Gemini API Key: ").strip()
            if not api_key:
                print("Error: Gemini API Key is required. Returning to menu.")
                continue
            
            print("\nInitializing Google Gemini (gemini-2.5-flash)...")
            llm = get_gemini_llm(api_key)
            
        elif choice == "2":
            # OpenRouter setup
            api_key = os.environ.get("OPENROUTER_API_KEY")
            if not api_key:
                api_key = input("Enter your OpenRouter API Key: ").strip()
            if not api_key:
                print("Error: OpenRouter API Key is required. Returning to menu.")
                continue
            
            # Free model registry
            free_models = {
                "1": "google/gemini-2.5-flash",
                "2": "meta-llama/llama-3.3-70b-instruct:free",
                "3": "deepseek/deepseek-r1:free",
                "4": "qwen/qwen-2.5-coder-32b-instruct:free",
                "5": "openrouter/free"
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
                # Fallback if user typed a custom model name directly
                model_name = model_choice
                
            print(f"\nInitializing OpenRouter ({model_name})...")
            llm = get_openrouter_llm(api_key, model_name)
            
        else:
            print("Invalid selection. Please choose 1, 2, or 3.")
            continue

        # 2. Define standard chain components
        # We use a simple prompt template & string output parser linked together with LCEL
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful and concise AI assistant."),
            ("user", "{user_input}")
        ])
        output_parser = StrOutputParser()
        
        # Simple chain: prompt | llm | output_parser
        chain = prompt | llm | output_parser
        
        print("\nInitialization successful!")
        print("-> Type your prompt below to chat.")
        print("-> Type 'menu' to switch provider, model, or keys.")
        print("-> Type 'exit' or 'quit' to close the application.")
        print("-" * 50)
        
        # 3. Chat loop
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
                response = chain.invoke({"user_input": user_input})
                print(f"\nResponse:\n{response}")
                print("-" * 50)
                
            except Exception as e:
                print(f"\nAn error occurred: {e}")
                print("-" * 50)
                
        if exit_app:
            break

if __name__ == "__main__":
    main()
