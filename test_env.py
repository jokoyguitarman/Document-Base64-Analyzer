import os

def check_env_vars():
    """Check if required environment variables are set"""
    print("=== Environment Variables Check ===\n")
    
    required_vars = {
        'SUPABASE_URL': 'Your Supabase project URL',
        'SUPABASE_SERVICE_ROLE_KEY': 'Your Supabase service role key',
        'OPENAI_API_KEY': 'Your OpenAI API key'
    }
    
    all_set = True
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            print(f"✓ {var}: Set ({len(value)} characters)")
        else:
            print(f"✗ {var}: Not set - {description}")
            all_set = False
    
    print(f"\nStatus: {'All variables set' if all_set else 'Missing variables'}")
    return all_set

if __name__ == "__main__":
    check_env_vars() 