# Contributions

This repository shows the SK-RAFT Python client and the getting-started examples. Only the SolidKosmos team changes the contents of this repository.

## Pull requests from persons outside SolidKosmos

SolidKosmos does not accept pull requests from persons outside SolidKosmos. SolidKosmos closes these pull requests without a review.

## Report a bug

Users can report bugs through GitHub Issues. Use an issue to report a bug in the client, in the examples or in the documents.

1. Go to the **Issues** tab of this repository.
2. Click **New issue**.
3. Select **Bug report**.
4. Complete all the fields of the template.
5. Click **Submit new issue**.

SolidKosmos examines each issue and replies in the issue.

> **Note:** Issues are public. Do not attach confidential design files, bitstreams, EBD files, LL files or licence data. If SolidKosmos must examine a confidential design, SolidKosmos will contact you directly.

For licence questions, commercial questions or questions about the SK-RAFT server, contact SolidKosmos through [www.solidkosmos.gr](https://www.solidkosmos.gr).

## Changes by the SolidKosmos team

Nobody pushes changes directly to the `main` branch. Each change goes into `main` through a pull request that the repository owner approves.

1. Make a new branch from `main`.
2. Do your changes in the new branch.
3. Write all documents and code comments in ASD-STE100 Simplified Technical English.
4. Run the examples that your change affects on a board.
5. Open a pull request to `main`. In the description, tell what you changed and why.
6. Wait for the approval of the repository owner. The repository owner merges the pull request.

### Add an example

1. Make a new folder in `get_started/`, next to `example1/` .. `example4/` and `hw/`.
2. Add a `README.md` to the new folder. Use the README of an existing example as a template.
3. If the example has a new design, add the VHDL sources to `get_started/hw/sources_1/new/` and the XDC files to `get_started/hw/xdc/<device>/`.
4. Add the example to the table in [`get_started/README.md`](get_started/README.md).

To add a new client, make a new folder in `api/` at the root of the repository. Add a `README.md` to the new folder.

## Licence

The Apache License 2.0 applies to all contents of this repository. Refer to [`LICENSE.md`](LICENSE.md).
