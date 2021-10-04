# Mock FS

## Purpose

This is a small, very limited and simple implementation of an in-memory filesystem,
written for use with ops.testing.Harness in the Operator Framework.  It aims to
implement a very basic level of functionality sufficient for wiring into a mock of the
Pebble file I/O APIs in the ops.testing.Harness class.

Benefits:

* Single file module with no dependencies beyond the Python standard library.
* Handles small files in memory and large files by using temporary files.
* Allows for opening files via file-like objects, regardless of whether they're memory-
  or file-backed.


This repository is being created primarily as a temporary spot for this code.
If it is later mainlined into the Operator Framework, this repository may be deleted.
