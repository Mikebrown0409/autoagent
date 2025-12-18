- Verify `hello.py` exists in workspace root and contains exactly: `def main(): print("Hello, World!")` and `if __name__ == "__main__": main()`
- If `hello.py` is missing or incorrect, create/overwrite `hello.py` with:
```
def main():
    print("Hello, World!")

if __name__ == "__main__":
    main()
```
- Execute `python hello.py` and capture console output
- Confirm execution output is exactly "Hello, World!" with no extra text or errors
- Create `README.md` in workspace root with content: "# Hello World App\n\nSimple Python script that prints 'Hello, World!' using a main function."
- Stage all changes with `git add .`
- Commit with `git commit -m "Complete hello.py implementation with README"`
- Push to remote with `git push`