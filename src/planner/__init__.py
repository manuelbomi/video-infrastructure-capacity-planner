"""video-infrastructure-capacity-planner

A sizing / capacity-planning calculator for video surveillance and video
analytics deployments. Given camera count, resolution, frame rate, codec,
retention policy, and the number of concurrent AI inference streams that
need to run, this package estimates the network bandwidth, storage, and GPU
capacity required, and recommends an edge / cloud / hybrid processing
architecture.

See the top-level README.md for the formulas used and the assumptions behind
them. All numeric assumptions (codec efficiency, GPU throughput) are clearly
labeled as illustrative examples that must be validated against real
encoder and hardware benchmarks before being used to quote a customer.
"""

__version__ = "0.1.0"
