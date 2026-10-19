# Amazon routes sample

`amazon_sample.json.gz` holds 60 routes from the training data of the 2021 Amazon
Last Mile Routing Research Challenge, extracted with `extract_amazon_sample.py`
(routes Amazon scored "High", at most five per station, seed 20261019). The
study (`code/amazon_benchmark.py`) uses the first 40 in sorted order.

Source: D. Merchán, J. Arora, J. Pachon, K. Konduri, M. Winkenbach, S. Parks and
J. Noszek, "2021 Amazon Last Mile Routing Research Challenge: Data Set",
Transportation Science (2022), https://doi.org/10.1287/trsc.2022.1173. Data at
https://registry.opendata.aws/amazon-last-mile-challenges

Copyright Amazon.com, Inc. or its affiliates. The data are licensed under the
Creative Commons Attribution-NonCommercial 4.0 International licence
(`LICENSE_CC_BY_NC_4.0.txt`). This file is a subset: routes were selected and
package records were summarised per stop (total service time, total volume,
time windows); nothing else was changed. It may not be used commercially. The
code in this repository keeps its own licence.

To rebuild the sample from the full data set:

    aws s3 cp --no-sign-request --recursive s3://amazon-last-mile-challenges/almrrc2021/almrrc2021-data-training/model_build_inputs/ amazon/
    python3 extract_amazon_sample.py amazon amazon
