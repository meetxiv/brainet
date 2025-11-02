"""
AST Parser Module - The Brain of Brainet

This module provides semantic code understanding through Python AST (Abstract Syntax Tree) parsing.
It extracts:
- Class definitions with methods and attributes
- Function definitions
- Import statements
- Global variables and constants
- Decorators

This enables brainet to understand code structure and relationships, not just diffs.
"""

import ast
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import re


class ASTParser:
    """
    Parse Python code using AST to extract semantic structure.
    
    This is the "brain" that gives brainet understanding of code beyond just diffs.
    """
    
    def __init__(self):
        """Initialize the AST parser."""
        self.parsed_files: Dict[str, Dict[str, Any]] = {}
        self._node_cache: Dict[str, ast.AST] = {}  # Cache parsed trees
    
    def parse_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Parse a Python file and extract code structure.
        
        Args:
            file_path: Path to the file being parsed
            content: File content as string
            
        Returns:
            Dictionary containing:
            {
                "classes": [list of class definitions],
                "functions": [list of function definitions],
                "imports": [list of imports],
                "globals": [list of global variables],
                "error": str (if syntax error occurred)
            }
        """
        if not file_path.endswith('.py'):
            return self._empty_structure(f"Not a Python file: {file_path}")
        
        try:
            # Parse the content into AST
            tree = ast.parse(content, filename=file_path)
            self._node_cache[file_path] = tree
            
            # Extract all structural elements
            structure = {
                "classes": self._extract_classes(tree, content),
                "functions": self._extract_functions(tree, content),
                "imports": self._extract_imports(tree),
                "globals": self._extract_globals(tree),
                "constants": self._extract_constants(tree),
                "error": None
            }
            
            # Cache the parsed structure
            self.parsed_files[file_path] = structure
            return structure
            
        except SyntaxError as e:
            error_msg = f"Syntax error at line {e.lineno}: {e.msg}"
            structure = self._empty_structure(error_msg)
            self.parsed_files[file_path] = structure
            return structure
        
        except Exception as e:
            error_msg = f"Parse error: {str(e)}"
            structure = self._empty_structure(error_msg)
            self.parsed_files[file_path] = structure
            return structure
    
    def _empty_structure(self, error: str = None) -> Dict[str, Any]:
        """Return empty structure with optional error message."""
        return {
            "classes": [],
            "functions": [],
            "imports": [],
            "globals": [],
            "constants": [],
            "error": error
        }
    
    def _extract_classes(self, tree: ast.AST, content: str) -> List[Dict]:
        """
        Extract all class definitions from AST.
        
        Returns list of class info including methods, attributes, and decorators.
        """
        classes = []
        content_lines = content.split('\n')
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Skip nested classes for now (only top-level and first-level)
                class_info = {
                    "name": node.name,
                    "line_start": node.lineno,
                    "line_end": node.end_lineno,
                    "docstring": ast.get_docstring(node),
                    "methods": [],
                    "attributes": [],
                    "base_classes": [],
                    "decorators": [self._get_decorator_name(d) for d in node.decorator_list],
                    "is_dataclass": self._is_dataclass(node)
                }
                
                # Extract base classes (inheritance)
                for base in node.bases:
                    base_name = self._get_name_from_node(base)
                    if base_name:
                        class_info["base_classes"].append(base_name)
                
                # Extract methods
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_info = self._extract_method_info(item, content_lines)
                        class_info["methods"].append(method_info)
                
                # Extract attributes (self.x = ... in __init__ and class-level)
                class_info["attributes"] = self._extract_class_attributes(node, content_lines)
                
                classes.append(class_info)
        
        return classes
    
    def _extract_method_info(self, node: ast.FunctionDef, content_lines: List[str]) -> Dict:
        """Extract detailed method information."""
        # Get parameter info with type hints
        params = []
        for arg in node.args.args:
            param_info = {
                "name": arg.arg,
                "type_hint": self._get_annotation_string(arg.annotation) if arg.annotation else None
            }
            params.append(param_info)
        
        # Get return type hint
        return_type = self._get_annotation_string(node.returns) if node.returns else None
        
        # Determine method type
        method_type = "method"
        if node.decorator_list:
            decorators = [self._get_decorator_name(d) for d in node.decorator_list]
            if "staticmethod" in decorators:
                method_type = "staticmethod"
            elif "classmethod" in decorators:
                method_type = "classmethod"
            elif "property" in decorators:
                method_type = "property"
        
        # Get method body summary (first few lines)
        body_lines = []
        if node.lineno and node.end_lineno:
            start = node.lineno - 1  # 0-indexed
            end = min(start + 10, node.end_lineno)  # Max 10 lines preview
            body_lines = content_lines[start:end]
        
        return {
            "name": node.name,
            "line_start": node.lineno,
            "line_end": node.end_lineno,
            "args": params,
            "return_type": return_type,
            "docstring": ast.get_docstring(node),
            "decorators": [self._get_decorator_name(d) for d in node.decorator_list],
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "method_type": method_type,
            "is_private": node.name.startswith('_') and not node.name.startswith('__'),
            "is_dunder": node.name.startswith('__') and node.name.endswith('__'),
            "body_preview": body_lines[:3]  # First 3 lines of implementation
        }
    
    def _extract_class_attributes(self, class_node: ast.ClassDef, content_lines: List[str]) -> List[Dict]:
        """
        Extract class attributes (both class-level and instance attributes).
        
        Instance attributes are found in __init__ (self.x = ...)
        Class attributes are defined directly in class body.
        """
        attributes = []
        seen_attrs = set()
        
        # Find __init__ method to extract instance attributes
        for item in class_node.body:
            if isinstance(item, ast.FunctionDef) and item.name == '__init__':
                # Walk through __init__ to find self.attribute assignments
                for stmt in ast.walk(item):
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Attribute):
                                if isinstance(target.value, ast.Name) and target.value.id == 'self':
                                    attr_name = target.attr
                                    if attr_name not in seen_attrs:
                                        # Try to infer type from assignment
                                        inferred_type = self._infer_type_from_value(stmt.value)
                                        
                                        attributes.append({
                                            "name": attr_name,
                                            "type": "instance",
                                            "inferred_type": inferred_type,
                                            "line": stmt.lineno
                                        })
                                        seen_attrs.add(attr_name)
        
        # Extract class-level attributes
        for item in class_node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        attr_name = target.id
                        if attr_name not in seen_attrs:
                            inferred_type = self._infer_type_from_value(item.value)
                            
                            attributes.append({
                                "name": attr_name,
                                "type": "class",
                                "inferred_type": inferred_type,
                                "line": item.lineno
                            })
                            seen_attrs.add(attr_name)
            
            # Handle annotated assignments (x: int = 5)
            elif isinstance(item, ast.AnnAssign):
                if isinstance(item.target, ast.Name):
                    attr_name = item.target.id
                    if attr_name not in seen_attrs:
                        type_hint = self._get_annotation_string(item.annotation)
                        
                        attributes.append({
                            "name": attr_name,
                            "type": "class",
                            "type_hint": type_hint,
                            "line": item.lineno
                        })
                        seen_attrs.add(attr_name)
        
        return attributes
    
    def _extract_functions(self, tree: ast.AST, content: str) -> List[Dict]:
        """
        Extract standalone functions (not methods inside classes).
        """
        functions = []
        content_lines = content.split('\n')
        
        # Get only module-level functions (not nested in classes)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_info = self._extract_function_info(node, content_lines)
                functions.append(func_info)
        
        return functions
    
    def _extract_function_info(self, node: ast.FunctionDef, content_lines: List[str]) -> Dict:
        """Extract detailed function information."""
        # Get parameter info with type hints
        params = []
        for arg in node.args.args:
            param_info = {
                "name": arg.arg,
                "type_hint": self._get_annotation_string(arg.annotation) if arg.annotation else None
            }
            params.append(param_info)
        
        # Get return type
        return_type = self._get_annotation_string(node.returns) if node.returns else None
        
        # Get function body preview
        body_lines = []
        if node.lineno and node.end_lineno:
            start = node.lineno - 1
            end = min(start + 10, node.end_lineno)
            body_lines = content_lines[start:end]
        
        return {
            "name": node.name,
            "line_start": node.lineno,
            "line_end": node.end_lineno,
            "args": params,
            "return_type": return_type,
            "docstring": ast.get_docstring(node),
            "decorators": [self._get_decorator_name(d) for d in node.decorator_list],
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "is_private": node.name.startswith('_') and not node.name.startswith('__'),
            "body_preview": body_lines[:3]
        }
    
    def _extract_imports(self, tree: ast.AST) -> List[Dict]:
        """
        Extract all import statements.
        
        Returns list of imports with module names and aliases.
        """
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        "module": alias.name,
                        "alias": alias.asname,
                        "type": "import",
                        "line": node.lineno
                    })
            
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                level = node.level  # For relative imports (from . import x)
                
                for alias in node.names:
                    imports.append({
                        "module": module,
                        "name": alias.name,
                        "alias": alias.asname,
                        "type": "from_import",
                        "level": level,
                        "line": node.lineno
                    })
        
        return imports
    
    def _extract_globals(self, tree: ast.AST) -> List[Dict]:
        """
        Extract global variables (module-level assignments).
        """
        globals_list = []
        
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        # Skip constants (uppercase names)
                        if not target.id.isupper():
                            inferred_type = self._infer_type_from_value(node.value)
                            
                            globals_list.append({
                                "name": target.id,
                                "line": node.lineno,
                                "inferred_type": inferred_type,
                                "is_constant": False
                            })
            
            # Handle type-annotated variables (x: int = 5)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    if not node.target.id.isupper():
                        type_hint = self._get_annotation_string(node.annotation)
                        
                        globals_list.append({
                            "name": node.target.id,
                            "line": node.lineno,
                            "type_hint": type_hint,
                            "is_constant": False
                        })
        
        return globals_list
    
    def _extract_constants(self, tree: ast.AST) -> List[Dict]:
        """
        Extract constants (uppercase global variables by convention).
        """
        constants = []
        
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        # Constants are UPPERCASE
                        if target.id.isupper():
                            inferred_type = self._infer_type_from_value(node.value)
                            
                            constants.append({
                                "name": target.id,
                                "line": node.lineno,
                                "inferred_type": inferred_type
                            })
        
        return constants
    
    # Helper methods
    
    def _get_decorator_name(self, decorator: ast.AST) -> str:
        """Extract decorator name from AST node."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            # Handle @obj.decorator
            value = self._get_name_from_node(decorator.value)
            return f"{value}.{decorator.attr}" if value else decorator.attr
        elif isinstance(decorator, ast.Call):
            # Handle @decorator() with parentheses
            return self._get_decorator_name(decorator.func)
        return "unknown"
    
    def _get_name_from_node(self, node: ast.AST) -> Optional[str]:
        """Extract name from various AST node types."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value = self._get_name_from_node(node.value)
            return f"{value}.{node.attr}" if value else node.attr
        elif isinstance(node, ast.Call):
            return self._get_name_from_node(node.func)
        return None
    
    def _get_annotation_string(self, annotation: ast.AST) -> str:
        """Convert type annotation AST to string."""
        if annotation is None:
            return None
        
        try:
            return ast.unparse(annotation)
        except:
            # Fallback for complex annotations
            if isinstance(annotation, ast.Name):
                return annotation.id
            elif isinstance(annotation, ast.Constant):
                return str(annotation.value)
            return "Any"
    
    def _infer_type_from_value(self, value_node: ast.AST) -> str:
        """
        Infer type from assignment value.
        
        Examples:
            x = 5 -> "int"
            x = "hello" -> "str"
            x = [] -> "list"
            x = {} -> "dict"
        """
        if isinstance(value_node, ast.Constant):
            return type(value_node.value).__name__
        elif isinstance(value_node, ast.List):
            return "list"
        elif isinstance(value_node, ast.Dict):
            return "dict"
        elif isinstance(value_node, ast.Set):
            return "set"
        elif isinstance(value_node, ast.Tuple):
            return "tuple"
        elif isinstance(value_node, ast.Call):
            # Try to get constructor name
            func_name = self._get_name_from_node(value_node.func)
            return func_name if func_name else "object"
        elif isinstance(value_node, ast.ListComp):
            return "list"
        elif isinstance(value_node, ast.DictComp):
            return "dict"
        elif isinstance(value_node, ast.SetComp):
            return "set"
        return "unknown"
    
    def _is_dataclass(self, class_node: ast.ClassDef) -> bool:
        """Check if class uses @dataclass decorator."""
        for decorator in class_node.decorator_list:
            dec_name = self._get_decorator_name(decorator)
            if 'dataclass' in dec_name.lower():
                return True
        return False
    
    # Search and Query Methods
    
    def search_by_keyword(self, keyword: str) -> List[Dict]:
        """
        Search all parsed files for entities matching keyword.
        
        Args:
            keyword: Search term (case-insensitive)
            
        Returns:
            List of matches with file, type, name, and line number
        """
        matches = []
        keyword_lower = keyword.lower()
        
        for file_path, structure in self.parsed_files.items():
            # Search classes
            for cls in structure.get("classes", []):
                if keyword_lower in cls["name"].lower():
                    matches.append({
                        "file": file_path,
                        "type": "class",
                        "name": cls["name"],
                        "line": cls["line_start"],
                        "docstring": cls.get("docstring")
                    })
                
                # Search methods within classes
                for method in cls.get("methods", []):
                    if keyword_lower in method["name"].lower():
                        matches.append({
                            "file": file_path,
                            "type": "method",
                            "name": f"{cls['name']}.{method['name']}",
                            "line": method["line_start"],
                            "docstring": method.get("docstring"),
                            "class": cls["name"]
                        })
                
                # Search attributes
                for attr in cls.get("attributes", []):
                    if keyword_lower in attr["name"].lower():
                        matches.append({
                            "file": file_path,
                            "type": "attribute",
                            "name": f"{cls['name']}.{attr['name']}",
                            "line": attr["line"],
                            "class": cls["name"]
                        })
            
            # Search standalone functions
            for func in structure.get("functions", []):
                if keyword_lower in func["name"].lower():
                    matches.append({
                        "file": file_path,
                        "type": "function",
                        "name": func["name"],
                        "line": func["line_start"],
                        "docstring": func.get("docstring")
                    })
            
            # Search global variables
            for glob in structure.get("globals", []):
                if keyword_lower in glob["name"].lower():
                    matches.append({
                        "file": file_path,
                        "type": "global",
                        "name": glob["name"],
                        "line": glob["line"]
                    })
        
        return matches
    
    def get_class_info(self, file_path: str, class_name: str) -> Optional[Dict]:
        """Get detailed info about a specific class."""
        if file_path not in self.parsed_files:
            return None
        
        structure = self.parsed_files[file_path]
        for cls in structure.get("classes", []):
            if cls["name"] == class_name:
                return cls
        
        return None
    
    def get_function_info(self, file_path: str, func_name: str) -> Optional[Dict]:
        """Get detailed info about a specific function."""
        if file_path not in self.parsed_files:
            return None
        
        structure = self.parsed_files[file_path]
        
        # Check standalone functions
        for func in structure.get("functions", []):
            if func["name"] == func_name:
                return func
        
        # Check methods in classes
        for cls in structure.get("classes", []):
            for method in cls.get("methods", []):
                if method["name"] == func_name:
                    return method
        
        return None
    
    def get_line_range_for_entity(self, file_path: str, entity_name: str) -> Optional[Tuple[int, int]]:
        """
        Get line range (start, end) for a class or function.
        
        Useful for extracting full context when entity was modified.
        """
        if file_path not in self.parsed_files:
            return None
        
        structure = self.parsed_files[file_path]
        
        # Check classes
        for cls in structure.get("classes", []):
            if cls["name"] == entity_name:
                return (cls["line_start"], cls["line_end"])
            
            # Check methods
            for method in cls.get("methods", []):
                if method["name"] == entity_name or f"{cls['name']}.{method['name']}" == entity_name:
                    return (method["line_start"], method["line_end"])
        
        # Check functions
        for func in structure.get("functions", []):
            if func["name"] == entity_name:
                return (func["line_start"], func["line_end"])
        
        return None
    
    def find_changed_entities(self, file_path: str, changed_lines: List[int]) -> List[Dict]:
        """
        Find which classes/functions were modified based on changed line numbers.
        
        Args:
            file_path: Path to file
            changed_lines: List of line numbers that changed
            
        Returns:
            List of entities (classes/functions) that contain changes
        """
        if file_path not in self.parsed_files:
            return []
        
        structure = self.parsed_files[file_path]
        changed_entities = []
        
        # Check classes
        for cls in structure.get("classes", []):
            if any(cls["line_start"] <= line <= cls["line_end"] for line in changed_lines):
                # Check which specific methods changed
                changed_methods = []
                for method in cls.get("methods", []):
                    if any(method["line_start"] <= line <= method["line_end"] for line in changed_lines):
                        changed_methods.append(method["name"])
                
                changed_entities.append({
                    "type": "class",
                    "name": cls["name"],
                    "line_start": cls["line_start"],
                    "line_end": cls["line_end"],
                    "changed_methods": changed_methods
                })
        
        # Check standalone functions
        for func in structure.get("functions", []):
            if any(func["line_start"] <= line <= func["line_end"] for line in changed_lines):
                changed_entities.append({
                    "type": "function",
                    "name": func["name"],
                    "line_start": func["line_start"],
                    "line_end": func["line_end"]
                })
        
        return changed_entities
    
    def get_summary(self, file_path: str) -> str:
        """
        Get a human-readable summary of file structure.
        
        Returns formatted string describing classes, functions, etc.
        """
        if file_path not in self.parsed_files:
            return f"File {file_path} not parsed"
        
        structure = self.parsed_files[file_path]
        
        if structure.get("error"):
            return f"Parse error: {structure['error']}"
        
        summary_parts = []
        
        # Classes
        classes = structure.get("classes", [])
        if classes:
            summary_parts.append(f"{len(classes)} class(es):")
            for cls in classes:
                methods_count = len(cls.get("methods", []))
                attrs_count = len(cls.get("attributes", []))
                summary_parts.append(f"  - {cls['name']}: {methods_count} methods, {attrs_count} attributes")
        
        # Functions
        functions = structure.get("functions", [])
        if functions:
            summary_parts.append(f"{len(functions)} function(s):")
            for func in functions:
                summary_parts.append(f"  - {func['name']}()")
        
        # Imports
        imports = structure.get("imports", [])
        if imports:
            summary_parts.append(f"{len(imports)} import(s)")
        
        return "\n".join(summary_parts) if summary_parts else "Empty file"
    
    def clear_cache(self):
        """Clear all cached parsed data."""
        self.parsed_files.clear()
        self._node_cache.clear()
