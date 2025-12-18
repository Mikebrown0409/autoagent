- Verify `hello.py` in workspace root contains exactly: `def main(): print("Hello, World!")\nif __name__ == "__main__": main()`
- If `hello.py` differs, overwrite with precise content:
```
def main():
    print("Hello, World!")

if __name__ == "__main__":
    main()
```
- Execute `python hello.py` in workspace root and confirm output is exactly "Hello, World!" with no extra text or errors
- Complete `README.md` in workspace root with full explanation of hello.py functionality and usage
- Add to `README.md`: "## Usage\nRun: `python hello.py`"
- Commit changes with message: "Finalize hello.py and complete README.md"