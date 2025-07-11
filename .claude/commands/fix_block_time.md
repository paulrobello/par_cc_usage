# Fix the current time block computation in the project

The current time block is not being computed correctly, the reference project `../ccusage` is computing it correctly.
You can run the ccusage using `npx https://pkg.pr.new/ryoppippi/ccusage@main blocks --live` you do not need to change folders to run it. It does run continuously and will need to stopped.
Do a deep dive on the ccusage project from json to display to see how this projects implementation differs.
The `uv run pccu monitor --snapshot` shows this projects current block start time does not match ccusage.
You can use the `uv run pccu debug-*` commands to debug the current block time computation.
You have full access to the ccusage code base, don't guess about what it is doing. Match its logic.
