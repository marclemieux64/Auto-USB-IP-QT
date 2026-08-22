#!/usr/bin/env python3
"""
Auto USB/IP Client entry point wrapper.
Delegates execution to main.py to maintain backward compatibility.
"""
from main import main

if __name__ == "__main__":
    main()
