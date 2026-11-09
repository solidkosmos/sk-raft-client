To install the client on a computer that has no internet access, make an offline bundle on a computer that has internet access:

```bash
python make_bundle.py --target linux-x86_64 --target windows-amd64 --python-version 3.11
```

- `--target` is the platform of the computer without internet access: `linux-x86_64`, `linux-aarch64` or `windows-amd64`. Repeat it for more platforms.
- `--python-version` is the Python version of that computer. Repeat it for more versions. The bundle must have the correct version, because `grpcio` contains compiled code.
- Without these options, the bundle is for the platform and the Python version that run the script.
- To pin the versions of the dependencies, give a requirements file with `--requirements`.

You can also run `bundler.sh` on Linux or `bundler.bat` on Windows. Without options, these scripts make a bundle for `linux-x86_64` and `windows-amd64`. They give other options to `make_bundle.py`, and they find a Python with pip for you.

The script writes an archive to `api/python/dist`. Copy the archive to the computer without internet access and extract it. Then run `./install.sh` on Linux or `install.bat` on Windows. The installer does not use the network. It installs the client and `pyserial`, which some examples use, into the active virtual environment, or else into `.venv` in the current directory. For more options, run `python install.py --help`.