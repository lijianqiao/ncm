import ast
from pathlib import Path
from typing import Dict, List, Tuple

class ParentTracker(ast.NodeVisitor):
    """Track parent-child relationships in AST."""
    def __init__(self):
        self.parents = {}
    
    def visit(self, node):
        for child in ast.iter_child_nodes(node):
            self.parents[child] = node
            self.visit(child)

def has_file_header(tree: ast.Module) -> bool:
    """Check if module has a docstring containing '@Author'."""
    if (tree.body and isinstance(tree.body[0], ast.Expr) and 
        isinstance(tree.body[0].value, ast.Constant) and
        isinstance(tree.body[0].value.value, str)):
        docstring = tree.body[0].value.value
        return '@Author' in docstring
    return False

def has_docstring(node) -> bool:
    """Check if a function/class has a docstring."""
    if (node.body and isinstance(node.body[0], ast.Expr) and
        isinstance(node.body[0].value, ast.Constant) and
        isinstance(node.body[0].value.value, str)):
        return True
    return False

def get_docstring(node) -> str:
    """Extract docstring from a node."""
    if (node.body and isinstance(node.body[0], ast.Expr) and
        isinstance(node.body[0].value, ast.Constant) and
        isinstance(node.body[0].value.value, str)):
        return node.body[0].value.value
    return ''

def is_google_style_docstring(docstring: str, has_args: bool, has_returns: bool) -> bool:
    """Check if docstring follows Google Style."""
    if not docstring:
        return False
    
    # Brief summary is ok, but if function has args/returns, should have Args:/Returns:
    if has_args and 'Args:' not in docstring and 'args:' not in docstring:
        return False
    if has_returns and 'Returns:' not in docstring and 'returns:' not in docstring:
        return False
    
    return True

def analyze_file(file_path: Path) -> Dict:
    """Analyze a single Python file."""
    result = {
        'file': str(file_path),
        'has_header': False,
        'missing_docstrings': [],
        'non_google_style': []
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=str(file_path))
        
        # Check file header
        result['has_header'] = has_file_header(tree)
        
        # Track parents
        tracker = ParentTracker()
        tracker.visit(tree)
        parents = tracker.parents
        
        # Collect class docstrings
        class_docstrings = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_docstrings[node.name] = has_docstring(node)
        
        # Analyze functions
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check if nested (parent is a function)
                parent = parents.get(node)
                is_nested = False
                while parent:
                    if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        is_nested = True
                        break
                    parent = parents.get(parent)
                
                if is_nested:
                    continue
                
                # Find containing class
                parent = parents.get(node)
                containing_class = None
                while parent:
                    if isinstance(parent, ast.ClassDef):
                        containing_class = parent.name
                        break
                    parent = parents.get(parent)
                
                func_name = node.name
                
                # Skip __init__ if class has docstring
                if func_name == '__init__' and containing_class:
                    if class_docstrings.get(containing_class, False):
                        continue
                
                # Build full function name
                if containing_class:
                    func_full_name = f"{containing_class}.{func_name}"
                else:
                    func_full_name = func_name
                
                # Check docstring
                has_doc = has_docstring(node)
                if not has_doc:
                    result['missing_docstrings'].append(func_full_name)
                else:
                    # Check Google Style
                    has_args = len(node.args.args) > 0
                    has_returns = node.returns is not None
                    if (has_args or has_returns):
                        docstring = get_docstring(node)
                        if not is_google_style_docstring(docstring, has_args, has_returns):
                            result['non_google_style'].append(func_full_name)
    
    except SyntaxError as e:
        result['error'] = f"Syntax error: {e}"
    except Exception as e:
        result['error'] = f"Error: {e}"
    
    return result

def main():
    celery_dir = Path('backend/app/celery')
    
    if not celery_dir.exists():
        print(f"Directory {celery_dir} does not exist!")
        return
    
    # Find all Python files
    python_files = list(celery_dir.rglob('*.py'))
    
    if not python_files:
        print(f"No Python files found in {celery_dir}")
        return
    
    print(f"Analyzing {len(python_files)} Python file(s) in {celery_dir}\n")
    print("=" * 80)
    
    files_missing_headers = []
    all_missing_docstrings = []
    all_non_google_style = []
    
    for file_path in sorted(python_files):
        result = analyze_file(file_path)
        
        if result.get('error'):
            print(f"\nERROR in {result['file']}: {result['error']}")
            continue
        
        if not result['has_header']:
            files_missing_headers.append(result['file'])
        
        if result['missing_docstrings']:
            all_missing_docstrings.extend([(result['file'], name) for name in result['missing_docstrings']])
        
        if result['non_google_style']:
            all_non_google_style.extend([(result['file'], name) for name in result['non_google_style']])
    
    # Print report
    print("\n" + "=" * 80)
    print("ANALYSIS REPORT")
    print("=" * 80)
    
    print(f"\n1. FILES MISSING HEADERS ({len(files_missing_headers)}):")
    if files_missing_headers:
        for file in files_missing_headers:
            print(f"   - {file}")
    else:
        print("   鉁?All files have headers")
    
    print(f"\n2. FUNCTIONS MISSING DOCSTRINGS ({len(all_missing_docstrings)}):")
    if all_missing_docstrings:
        for file, func in all_missing_docstrings:
            print(f"   - {file}: {func}")
    else:
        print("   鉁?All functions have docstrings")
    
    print(f"\n3. FUNCTIONS WITH NON-GOOGLE-STYLE DOCSTRINGS ({len(all_non_google_style)}):")
    if all_non_google_style:
        for file, func in all_non_google_style:
            print(f"   - {file}: {func}")
    else:
        print("   鉁?All docstrings follow Google Style")
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    main()
