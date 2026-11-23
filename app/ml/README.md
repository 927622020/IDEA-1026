# ML module

The first milestone is data definition and baseline evaluation, not training a model
on invented data. Define a versioned feature contract and assemble historical,
time-aligned store-SKU observations before training LightGBM.

Candidate target: whether a SKU-store combination experiences a stockout within
the chosen prediction horizon. Avoid leakage: features must only contain
information available at prediction time.
