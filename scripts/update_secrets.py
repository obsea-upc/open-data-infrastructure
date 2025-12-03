"""
Updates secrets
"""
import random
import shutil
import secrets
import rich
import os
import datetime
import string

def update_secrets_file(filename: str):
    """
    This function will randomly generate new passwords and tokens for all services
    :param filename:
    :return:
    """


    if not os.path.exists(filename):
        rich.print("Creating secrets.env file from template")
        shutil.copy("/opt/odi/secrets.env.template", "/opt/odi/secrets.env")
    else:
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = os.path.dirname(filename) + "/." + os.path.basename(filename) + ".old." + now
        rich.print(f"Creating backup file {backup}")
        shutil.copy(filename, backup)

    new_contents = []
    with open(filename) as f:
        contents = f.readlines()

    ignore = ["EMAIL_SMPT_PASSWORD"]
    rich.print("Updating passwords:")

    for line in contents:
        if "PASSWORD" in line:
            key, password = line.split("=")
            if key not in ignore:
                rich.print(f"    updating '{key}'")
                n = random.randint(50, 70)
                alphabet = string.ascii_letters + string.digits
                new_pass = ''.join(secrets.choice(alphabet) for i in range(n))
                line = f"{key}={new_pass}\n"
        new_contents += line

    with open(filename, "w") as f:
        f.writelines(new_contents)

    rich.print("f[green]passwords updated!")



