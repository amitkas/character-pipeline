Run the Arbi video pipeline using **Grok Imagine Video** (xAI) for video generation instead of Kling. Same pipeline as /video but faster (~2 min) and cheaper (~$0.57).

Uses image-to-video, 10s duration, 1:1 square, 720p, with troll voice instructions in the prompt.

Execute the pipeline by running:

```bash
python3 main.py --grok
```

After the run completes, report the results: event title, final video path (in the output/ directory), and any errors. Check the logs directory for the JSON summary.
