import subprocess
import shutil
import os
import click


def get_mongodb_paths():
    """Get standardized paths for MongoDB files."""
    base_dir = os.path.join(os.getcwd(), ".mongodb")
    paths = {
        "base_dir": base_dir,
        "data_dir": os.path.join(base_dir, "data"),
        "log_file": os.path.join(base_dir, "logs", "mongodb.log"),
        "pid_file": os.path.join(base_dir, "mongodb.pid"),
    }
    # Create directories if they don't exist
    os.makedirs(paths["data_dir"], exist_ok=True)
    os.makedirs(os.path.dirname(paths["log_file"]), exist_ok=True)
    return paths


def start_mongodb(config, method):
    db_url = getattr(config, "DATABASE_URL", None)
    click.echo(f"Current DATABASE_URL: {db_url}")

    if not db_url or not db_url.startswith("mongodb://"):
        db_url = f"mongodb://localhost:27017/{config.DB_NAME}"
        click.echo(f"Setting DATABASE_URL to: {db_url}")
        config.update_config_file("DATABASE_URL", db_url)

    if method == "docker":
        start_docker_mongodb(config.DB_NAME, config.ENV)
    elif method == "local":
        start_local_mongodb(config.DB_NAME)
    else:
        provide_manual_instructions(db_url)


def stop_mongodb(env, method):
    if method == "docker":
        stop_docker_mongodb(env)
    elif method == "local":
        stop_local_mongodb()
    else:
        click.echo(
            "For manual setups, please stop your MongoDB instance using your preferred method."
        )


def start_docker_mongodb(db_name, env):
    if not shutil.which("docker"):
        click.echo(
            "Docker is not installed. Please install Docker to use this feature."
        )
        return

    container_name = f"metro-mongodb-{env}"
    cmd = [
        "docker",
        "run",
        "-d",
        "--name",
        container_name,
        "-p",
        "27017:27017",
        "-e",
        f"MONGO_INITDB_DATABASE={db_name}",
        "mongo:latest",
    ]

    try:
        subprocess.run(cmd, check=True)
        click.echo(f"MongoDB container '{container_name}' is running.")
    except subprocess.CalledProcessError as e:
        click.echo(f"Failed to start MongoDB container: {e}")


def start_local_mongodb(db_name):
    if not shutil.which("mongod"):
        click.echo(
            "MongoDB is not installed. Please install MongoDB to use this feature."
        )
        return

    paths = get_mongodb_paths()

    # Check if MongoDB is already running
    try:
        subprocess.run(["pgrep", "mongod"], check=True, capture_output=True)
        click.echo("MongoDB is already running")
        return
    except subprocess.CalledProcessError:
        pass

    cmd = [
        "mongod",
        "--dbpath",
        paths["data_dir"],
        "--fork",
        "--logpath",
        paths["log_file"],
        "--pidfilepath",
        paths["pid_file"],
    ]

    try:
        subprocess.run(cmd, check=True)
        click.echo(
            f"Local MongoDB instance started. Data directory: {paths['data_dir']}"
        )
    except subprocess.CalledProcessError as e:
        click.echo(f"Failed to start local MongoDB: {e}")


def provide_manual_instructions(db_url):
    click.echo("Manual database setup instructions:")
    click.echo(f"1. Install MongoDB on your system if not already installed.")
    click.echo(f"2. Start MongoDB using your preferred method.")
    click.echo(f"3. Ensure your MongoDB is accessible at: {db_url}")
    click.echo(f"4. Create a database named: {db_url.split('/')[-1]}")
    click.echo("5. Update your Metro configuration if necessary.")


def stop_docker_mongodb(env):
    container_name = f"metro-mongodb-{env}"
    try:
        subprocess.run(["docker", "stop", container_name], check=True)
        subprocess.run(["docker", "rm", container_name], check=True)
        click.echo(
            f"MongoDB container '{container_name}' has been stopped and removed."
        )
    except subprocess.CalledProcessError as e:
        click.echo(f"Failed to stop or remove MongoDB container: {e}")


def stop_local_mongodb():
    paths = get_mongodb_paths()

    def find_mongod_pid():
        try:
            ps_output = subprocess.run(
                ["ps", "-ef", "|", "grep", "mongod"],
                capture_output=True,
                text=True,
                shell=True,
            )
            for line in ps_output.stdout.splitlines():
                if "mongod --dbpath" in line and not "grep mongod" in line:
                    return int(line.split()[1])
        except (subprocess.CalledProcessError, ValueError, IndexError):
            return None
        return None

    try:
        # Try to get PID from file first
        pid = None
        if os.path.exists(paths["pid_file"]):
            try:
                with open(paths["pid_file"]) as f:
                    pid = int(f.read().strip())
            except (ValueError, FileNotFoundError):
                pass

        # If no PID from file, try to find process
        if pid is None:
            pid = find_mongod_pid()

        if pid:
            try:
                import signal

                os.kill(pid, signal.SIGTERM)
                click.echo("Local MongoDB instance has been stopped.")
            except ProcessLookupError:
                click.echo(
                    "MongoDB process not found. It may have already been stopped."
                )
            except PermissionError:
                click.echo("Permission denied when trying to stop MongoDB.")
        else:
            click.echo("No running MongoDB instance found.")

        # Clean up PID file if it exists
        if os.path.exists(paths["pid_file"]):
            try:
                os.remove(paths["pid_file"])
            except FileNotFoundError:
                pass

    except Exception as e:
        click.echo(f"Error stopping MongoDB: {e}")
