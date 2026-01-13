# IR Tester - Packaging

This directory contains all artifacts needed to create the IR Tester `.deb` package.

## Structure

```
packaging/
├── assets/
│   ├── icons/
│   │   └── ir-tester.svg    # Application icon
│   └── ir-tester.desktop    # Desktop menu entry
├── debian/
│   ├── control              # Package metadata
│   ├── postinst             # Post-install script
│   └── postrm               # Post-remove script
├── build-deb.sh             # Build script
└── README.md                # This file
```

## Build

To create the `.deb` package:

```bash
cd packaging
./build-deb.sh
```

The package will be generated at `packaging/dist/ir-tester_<VERSION>_amd64.deb`.

## Installation

```bash
sudo dpkg -i dist/ir-tester_<VERSION>_amd64.deb
sudo apt install -f  # If there are missing dependencies
```

## Uninstall

```bash
sudo dpkg -r ir-tester
```
