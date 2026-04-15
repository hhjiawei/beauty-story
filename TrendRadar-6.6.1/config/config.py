import os

base_dir = os.path.dirname(os.path.abspath(__file__))

print(base_dir)  # D:\beauty-story\TrendRadar-6.6.1\config

config_yaml = os.path.join(base_dir, "config.yaml")
timeline = os.path.join(base_dir, "timeline.yaml")
frequency_words = os.path.join(base_dir, "frequency_words.txt")
ai_interests = os.path.join(base_dir, "ai_interests.txt")
ai_analysis_prompt = os.path.join(base_dir, "ai_analysis_prompt.txt")
ai_translation_prompt = os.path.join(base_dir, "ai_translation_prompt.txt")
