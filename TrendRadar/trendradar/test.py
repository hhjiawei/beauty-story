import os

base_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(base_dir, "config", "config.yaml")

print(base_dir)
print(config_path)
