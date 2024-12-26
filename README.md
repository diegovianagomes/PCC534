# Video Evaluation

This project automates the process of fetching YouTube videos related to algorithms and data structures, evaluates their quality and teaching methodology, and saves the results in both an Excel file and a database. The evaluation uses the gemini-2.0-flash-exp model to analyze the content for clarity, engagement, and effectiveness in teaching key computer science topics.

## Features

- **YouTube Video Search** 
Searches for YouTube videos based on a query, filtering by date, duration, and quality.
- **AI-Powered Video Evaluation**
Uses the Gemini AI model to evaluate video content for its educational quality on topics like arrays, linked lists, stacks, and more.
- **Excel Export**
 Saves video data and evaluations to an Excel file for offline access.
- **Database Integration**
 Stores video information and analysis in a Supabase database, avoiding duplicate entries.
- **Configurable Settings**
 Loads API keys and configuration details from environment variables for secure and flexible use.

---

## Installation
```bash
pip install -r requirements.txt
```

## Create a .env file with the following variables:
```bash
YOUTUBE_API_KEY=<your-youtube-api-key>
GEMINI_API_KEY=<your-gemini-api-key>
SUPABASE_URL=<your-supabase-url>
SUPABASE_KEY=<your-supabase-key>
```

## Run
```bash
python youtube_scrapper.py
```

---
## Usage
### Running the Script
By default, the script searches for videos on YouTube using the query "Algorithm+Advent of Code+Python+2024". This can be changed by modifying the query variable in the main function.
The results are analyzed, saved to an Excel file, and stored in a Supabase database.
### Output
Excel File: Contains video titles, descriptions, channels, links, and qualitative analyses.
Database Table: Stores the same data for further querying and analytics.
## Key Functions
### YouTube Video Search
get_YT(api_key): Returns an instance of the YouTube Data API service.
search_videos(youtube, query, days, max_results): Fetches videos based on search criteria.
### Evaluation
evaluate_video(title, description, channel, gemini_key): Analyzes the video content using the Gemini AI model.
### Storage
save_excel(data, file_name): Saves video data to an Excel file.

---
## Project Structure
```bash
.
├── script_name.py         # Main script
├── requirements.txt       # Python dependencies
├── .env                   # Configuration file (not included in the repo)
└── README.md              # Project documentation

```
---
## Contribution
- Fork the repository.
- Create a new branch:
```bash
git checkout -b feature-branch-name
```
-Commit your changes:
```bash
git commit -m "Add your message here"
```
- Push the branch:
```bash
git push origin feature-branch-name
```
- Open a pull request.

---

## Citation
Please cite the following repo if you use:

```latex
@misc{Gomes2024,
  author = {Diego, V.G},
  title = {Video Evaluation},
  year = {2024},
  publisher = {GitHub},
  journal = {GitHub repository},
  howpublished = {\url{https://github.com/diegovianagomes/Video-Evaluation}}
}
```


