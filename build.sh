#!/bin/bash
# Layer 1a — stamp a unique BUILD_ID into the build artifact.
# In a real pipeline: replace dist/index.html with your actual output file.

set -euo pipefail

COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "nogit")
BUILD_ID="build-$(date +%s)-${COMMIT}"
DIST="dist"

mkdir -p "$DIST"

cat > "$DIST/index.html" << EOF
<!DOCTYPE html>
<html>
<head>
  <meta name="x-build-id" content="${BUILD_ID}">
  <title>FrontierTower</title>
</head>
<body>
  <h1>FrontierTower Masterclass</h1>
  <p>13 labs complete.</p>
</body>
</html>
EOF

echo "BUILD_ID=${BUILD_ID}"
echo "$BUILD_ID" > dist/.build_id
