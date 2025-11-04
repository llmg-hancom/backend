from os import environ as env


def check_env_vars():
    required_vars = [
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_NAME",
        "JWT_SECRET_KEY",
    ]

    missing_vars = [var for var in required_vars if not env.get(var)]

    if missing_vars:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )
