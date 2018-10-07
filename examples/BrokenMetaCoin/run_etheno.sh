echo "Running the custom Manticore script ExploitMetaCoinManticoreScript.py"
# Set the max depth for Manticore to 2 because this script only needs to
# find a sequence of two transactions to exploit the bug
etheno --manticore --truffle --ganache --manticore-max-depth 2 -r ExploitMetaCoinManticoreScript.py

echo "Running a full Manticore analysis with standard vulnerability detectors (this can take roughly 30 minutes)"
# Set the max depth for Manticore to 2 because we can get ~98% coverage
# with that setting, and it drastically reduces compute time
etheno -m -t -g --manticore-max-depth 2
