#!/bin/bash
# Build the ITOR manuscript and its Supporting Information.
# Regenerate inputs first: cd code && PYTHONPATH=. python3 itor_tables.py && python3 build_itor_si.py
set -e
cd "$(dirname "$0")"
for doc in supporting_information routing_model_itor; do
  pdflatex -interaction=nonstopmode $doc.tex >/dev/null || true
  bibtex $doc >/dev/null || true
done
for i in 1 2; do
  pdflatex -interaction=nonstopmode supporting_information.tex >/dev/null || true
  # only the SI's labels go to the main text (not its citations)
  grep '^\\newlabel' supporting_information.aux > si_labels.aux
  pdflatex -interaction=nonstopmode routing_model_itor.tex >/dev/null || true
done
for doc in supporting_information routing_model_itor; do
  echo "$doc: $(pdfinfo $doc.pdf | awk '/Pages/{print $2}') pages, $(grep -c 'Overfull' $doc.log) overfull, $(grep -c 'undefined' $doc.log) undefined"
done
