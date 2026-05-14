import subprocess

def main():
    try:
        output = subprocess.check_output(["docker", "compose", "logs", "--no-log-prefix", "backend"], stderr=subprocess.STDOUT)
        with open("docker_logs.txt", "wb") as f:
            f.write(output)
    except subprocess.CalledProcessError as e:
        with open("docker_logs.txt", "wb") as f:
            f.write(e.output)

if __name__ == "__main__":
    main()
