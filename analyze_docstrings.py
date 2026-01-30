import ast
import os
from pathlib import Path
from typing import List, Tuple, Dict, Optional

class DocstringAnalyzer(ast.NodeVisitor):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.has_header = False
        self.functions_missing_docstring = []
        self.functions_non_google_style = []
        self.current_class: Optional[str] = None
        self.class_docstrings: Dict[str, bool] = {}
        
    def visit_Module(self, node):
        # Check for module-level docstring with @Author
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
            docstring = node.body[0].value.value
            if isinstance(docstring, str) and "@Author" in docstring:
                self.has_header = True
        self.generic_visit(node)
    
    def visit_ClassDef(self, node):
        # Check if class has docstring
        class_has_docstring = (
            node.body and 
            isinstance(node.body[0], ast.Expr) and 
            isinstance(node.body[0].value, ast.Constant) and
            isinstance(node.body[0].value.value, str)
        )
        self.class_docstrings[node.name] = class_has_docstring
        
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class
    
    def visit_FunctionDef(self, node):
        self._check_function(node, is_async=False)
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node):
        self._check_function(node, is_async=True)
        self.generic_visit(node)
    
    def _has_meaningful_args(self, node) -> bool:
        """Check if function has meaningful arguments (excluding self/cls)."""
        if not node.args.args:
            return False
        
        # Check if first arg is self or cls
        first_arg = node.args.args[0].arg if node.args.args else None
        if first_arg in ("self", "cls"):
            # Has more than just self/cls
            return len(node.args.args) > 1
        
        # Has at least one argument
        return len(node.args.args) > 0
    
    def _check_function(self, node, is_async: bool):
        # Skip __init__ if class has docstring
        if node.name == "__init__" and self.current_class:
            if self.class_docstrings.get(self.current_class, False):
                return  # Class has docstring, skip __init__
        
        # Get function docstring
        docstring = ast.get_docstring(node)
        
        # Check if it's a simple dependency injection function
        is_di_function = (
            node.name.startswith("get_") and 
            (node.name.endswith("_crud") or node.name.endswith("_service") or "_service" in node.name)
        )
        
        if not docstring:
            # Missing docstring
            if not is_di_function:  # Don't report DI functions without docstrings
                func_name = f"{self.current_class}.{node.name}" if self.current_class else node.name
                self.functions_missing_docstring.append(func_name)
        else:
            # Has docstring, check Google Style
            if is_di_function and len(docstring.split("\n")) == 1:
                # Simple one-line docstring for DI function is OK
                return
            
            # Check if function has arguments or returns
            has_args = self._has_meaningful_args(node)
            has_returns = node.returns is not None
            
            # Check for Google Style
            if has_args or has_returns:
                needs_args = has_args and "Args:" not in docstring
                needs_returns = has_returns and "Returns:" not in docstring
                
                if needs_args or needs_returns:
                    # Check if it's just a brief summary (short docstring)
                    lines = [line.strip() for line in docstring.split("\n") if line.strip() and not line.strip().startswith(":")]
                    if len(lines) > 3:  # More than brief summary
                        func_name = f"{self.current_class}.{node.name}" if self.current_class else node.name
                        self.functions_non_google_style.append(func_name)

def analyze_file(file_path: str) -> Tuple[bool, List[str], List[str]]:
    """Analyze a Python file for docstring compliance."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        tree = ast.parse(content, filename=file_path)
        analyzer = DocstringAnalyzer(file_path)
        analyzer.visit(tree)
        
        return analyzer.has_header, analyzer.functions_missing_docstring, analyzer.functions_non_google_style
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
        return False, [], []

def main():
    base_dir = Path("backend/app/api")
    files_to_check = []
    
    # Collect all Python files
    for pattern in ["**/*.py"]:
        files_to_check.extend(base_dir.glob(pattern))
    
    # Also check v1/endpoints
    endpoints_dir = Path("backend/app/api/v1/endpoints")
    if endpoints_dir.exists():
        files_to_check.extend(endpoints_dir.glob("*.py"))
    
    files_to_check = sorted(set(files_to_check))
    
    files_missing_header = []
    all_missing_docstrings = {}
    all_non_google_style = {}
    
    for file_path in files_to_check:
        relative_path = file_path.relative_to(Path("backend"))
        has_header, missing_docstrings, non_google_style = analyze_file(str(file_path))
        
        if not has_header:
            files_missing_header.append(str(relative_path))
        
        if missing_docstrings:
            all_missing_docstrings[str(relative_path)] = missing_docstrings
        
        if non_google_style:
            all_non_google_style[str(relative_path)] = non_google_style
    
    # Print report
    print("=" * 80)
    print("DOCSTRING ANALYSIS REPORT")
    print("=" * 80)
    print()
    
    if files_missing_header:
        print("FILES MISSING HEADERS (module-level docstring with @Author):")
        print("-" * 80)
        for file in files_missing_header:
            print(f"  - {file}")
        print()
    else:
        print("鉁?All files have headers")
        print()
    
    if all_missing_docstrings:
        print("FUNCTIONS/METHODS MISSING DOCSTRINGS:")
        print("-" * 80)
        for file, funcs in all_missing_docstrings.items():
            print(f"  {file}:")
            for func in funcs:
                print(f"    - {func}")
        print()
    else:
        print("鉁?All functions/methods have docstrings")
        print()
    
    if all_non_google_style:
        print("FUNCTIONS/METHODS WITH NON-GOOGLE-STYLE DOCSTRINGS:")
        print("(Functions with args/returns should have 'Args:' and 'Returns:' sections)")
        print("-" * 80)
        for file, funcs in all_non_google_style.items():
            print(f"  {file}:")
            for func in funcs:
                print(f"    - {func}")
        print()
    else:
        print("鉁?All docstrings follow Google Style")
        print()
    
    print("=" * 80)
    print(f"Summary: {len(files_missing_header)} files missing headers, "
          f"{sum(len(f) for f in all_missing_docstrings.values())} functions missing docstrings, "
          f"{sum(len(f) for f in all_non_google_style.values())} functions with non-Google-style docstrings")
    print("=" * 80)

if __name__ == "__main__":
    main()
