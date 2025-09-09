import os
import click
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

def get_api_key() -> Optional[str]:
    """Get the API key from environment or .env file."""
    # First try environment variable
    api_key = os.environ.get('VENICE_API_KEY')
    if api_key:
        return api_key
    
    # Then try .env file
    env_path = Path('.env')
    if env_path.exists():
        load_dotenv(env_path)
        return os.environ.get('VENICE_API_KEY')
    
    return None

@click.group()
def cli():
    """Venice SDK command-line interface."""
    pass

@cli.command()
@click.argument('api_key')
def auth(api_key: str):
    """Set your Venice API key.
    
    This command will store your API key in the .env file in the current directory.
    If no .env file exists, it will be created.
    """
    # Get the path to the .env file
    env_path = Path('.env')
    
    # Create .env file if it doesn't exist
    if not env_path.exists():
        env_path.touch()
    
    # Set the API key without quotes
    with open(env_path, 'w') as f:
        f.write(f'VENICE_API_KEY={api_key}\n')
    click.echo("API key has been set successfully!")

@cli.command()
def status():
    """Check the current authentication status."""
    api_key = get_api_key()
    
    if api_key:
        click.echo("✅ API key is set")
        # Show first 4 and last 4 characters of the key
        masked_key = f"{api_key[:4]}...{api_key[-4:]}"
        click.echo(f"Key: {masked_key}")
    else:
        click.echo("❌ No API key is set")
        click.echo("Use 'venice auth <your-api-key>' to set your API key")

def main():
    cli()

if __name__ == '__main__':
    main() 