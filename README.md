# workout-analysis

Python tools for fetching, analyzing, and visualizing workout data from Strava
and Google Sheets, with export to Hugo static site.

## setup

```bash
# create virtual environment
python -m venv .venv
source .venv/bin/activate

# install dependencies
pip install -r requirements.txt

# configure strava credentials
cp .env.example .env
# edit .env with your client_id and client_secret
```

## strava authentication

1. create an app at <https://www.strava.com/settings/api>
2. set callback domain to `localhost`
3. add client_id and client_secret to `.env`
4. run oauth flow:

```bash
python run.py auth
```

1. copy the refresh token to `.env`

## usage

```bash
# fetch fresh data from strava
python run.py fetch

# show summary stats
python run.py analyze

# export to hugo site
python run.py export

# generate charts and maps
python run.py visualize

# run full pipeline
python run.py all
```

## data sources

- **strava**: runs, walks, rides fetched via api
- **google sheets**: lifting workouts exported as tsv to `data/workouts.tsv`

## tests

```bash
python -m pytest tests/ -v
```
