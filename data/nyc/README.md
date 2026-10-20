# New York taxi trips (not stored here)

`code/nyc_calibration.py` reads the NYC Taxi & Limousine Commission yellow-taxi trip
records for January, February and March 2024 (about 160 MB in total). They are
public and are not copied into this repository. Download them into this folder:

    curl -O https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet
    curl -O https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-02.parquet
    curl -O https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-03.parquet

Source page: https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
The fitted values are in `results/nyc_calibration.json`.
