"""
Project Context Module - Source #5

Extracts project-wide context including structure, dependencies, and relationships.
This provides the AI with understanding of the broader codebase beyond individual files.

This module:
- Extracts project metadata (name, version, description)
- Builds file tree structure
- Parses dependencies from various package managers
- Finds configuration files
- Extracts documentation
- Builds module dependency graph
"""

from pathlib import Path
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
import json
import re


@dataclass
class Dependency:
    """Represents a project dependency."""
    name: str
    version: str = ""
    type: str = "runtime"  # runtime, dev, optional


@dataclass
class ProjectMetadata:
    """Complete project metadata."""
    project_name: str
    project_type: str
    dependencies: List[Dependency] = field(default_factory=list)
    total_files: int = 0
    total_lines: int = 0
    file_types: Dict[str, int] = field(default_factory=dict)
    config_files: List[str] = field(default_factory=list)


class ProjectContext:
    """
    Extract project-wide context and relationships.
    
    This is Source #5 in the 5-source architecture - provides project structure understanding.
    """
    
    def __init__(self, project_root: Path):
        """
        Initialize project context extractor.
        
        Args:
            project_root: Path to project root directory
        """
        self.project_root = Path(project_root)
    
    def extract_context(self) -> ProjectMetadata:
        """
        Extract project metadata in standardized format.
        
        This is the main API method used by context_capture.
        
        Returns:
            ProjectMetadata object with all project information
        """
        try:
            project_name = self._get_project_name()
            project_type = self._detect_project_type()
            
            # Get dependencies
            deps = self._get_dependencies()
            dependencies = []
            for dep_name, dep_version in deps.items():
                dependencies.append(Dependency(
                    name=dep_name,
                    version=dep_version,
                    type="runtime"
                ))
            
            # Get dev dependencies
            dev_deps = self._get_dev_dependencies()
            for dep_name, dep_version in dev_deps.items():
                dependencies.append(Dependency(
                    name=dep_name,
                    version=dep_version,
                    type="dev"
                ))
            
            # Get project statistics
            stats = self._get_project_statistics()
            
            # Get config files
            config_files = self._find_config_files()
            
            return ProjectMetadata(
                project_name=project_name,
                project_type=project_type,
                dependencies=dependencies,
                total_files=stats.get('total_files', 0),
                total_lines=stats.get('total_lines', 0),
                file_types=stats.get('file_types', {}),
                config_files=config_files
            )
        except Exception:
            # Return minimal metadata on error
            return ProjectMetadata(
                project_name=self.project_root.name,
                project_type="unknown"
            )
    
    def get_project_context(self) -> Dict[str, Any]:
        """
        Extract comprehensive project context.
        
        Legacy method - kept for backward compatibility.
        
        Returns dictionary with all project metadata, structure, and relationships.
        """
        return {
            "project_name": self._get_project_name(),
            "project_metadata": self._get_project_metadata(),
            "structure": self._build_file_tree(),
            "dependencies": self._get_dependencies(),
            "dev_dependencies": self._get_dev_dependencies(),
            "config_files": self._find_config_files(),
            "documentation": self._extract_documentation(),
            "project_type": self._detect_project_type(),
            "statistics": self._get_project_statistics()
        }
    
    def _get_project_name(self) -> str:
        """Get project name from various sources."""
        # Try setup.py
        setup_py = self.project_root / "setup.py"
        if setup_py.exists():
            try:
                with open(setup_py, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
                    if match:
                        return match.group(1)
            except:
                pass
        
        # Try pyproject.toml
        pyproject = self.project_root / "pyproject.toml"
        if pyproject.exists():
            try:
                with open(pyproject, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
                    if match:
                        return match.group(1)
            except:
                pass
        
        # Try package.json (Node.js)
        package_json = self.project_root / "package.json"
        if package_json.exists():
            try:
                with open(package_json, 'r', encoding='utf-8', errors='ignore') as f:
                    data = json.load(f)
                    if "name" in data:
                        return data["name"]
            except:
                pass
        
        # Fallback to directory name
        return self.project_root.name
    
    def _get_project_metadata(self) -> Dict[str, str]:
        """Extract project metadata (version, description, author, etc.)."""
        metadata = {}
        
        # Try setup.py
        setup_py = self.project_root / "setup.py"
        if setup_py.exists():
            try:
                with open(setup_py, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    # Extract version
                    version_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
                    if version_match:
                        metadata["version"] = version_match.group(1)
                    
                    # Extract description
                    desc_match = re.search(r'description\s*=\s*["\']([^"\']+)["\']', content)
                    if desc_match:
                        metadata["description"] = desc_match.group(1)
                    
                    # Extract author
                    author_match = re.search(r'author\s*=\s*["\']([^"\']+)["\']', content)
                    if author_match:
                        metadata["author"] = author_match.group(1)
            except:
                pass
        
        # Try package.json
        package_json = self.project_root / "package.json"
        if package_json.exists():
            try:
                with open(package_json, 'r', encoding='utf-8', errors='ignore') as f:
                    data = json.load(f)
                    if "version" in data:
                        metadata["version"] = data["version"]
                    if "description" in data:
                        metadata["description"] = data["description"]
                    if "author" in data:
                        metadata["author"] = data["author"]
            except:
                pass
        
        return metadata
    
    def _build_file_tree(self, max_depth: int = 3) -> Dict:
        """
        Build a tree structure of project files.
        
        Args:
            max_depth: Maximum directory depth to traverse
            
        Returns:
            Nested dictionary representing directory structure
        """
        def should_ignore(path: Path) -> bool:
            """Check if path should be ignored."""
            ignore_patterns = {
                '.git', '.brainet', '__pycache__', 'node_modules', 
                '.venv', 'venv', 'env', 'dist', 'build', '.egg-info',
                '.pytest_cache', '.mypy_cache', '.tox', 'coverage',
                '.DS_Store', 'Thumbs.db'
            }
            
            return (
                path.name.startswith('.') and path.name not in {'.gitignore', '.env.example'} or
                path.name in ignore_patterns or
                any(pattern in path.name for pattern in ignore_patterns)
            )
        
        def build_tree(path: Path, depth: int = 0) -> Dict:
            """Recursively build directory tree."""
            if depth > max_depth or should_ignore(path):
                return None
            
            if path.is_file():
                return {
                    "type": "file",
                    "size": path.stat().st_size,
                    "extension": path.suffix
                }
            
            # Directory
            tree = {"type": "directory", "children": {}}
            
            try:
                for child in sorted(path.iterdir()):
                    if not should_ignore(child):
                        subtree = build_tree(child, depth + 1)
                        if subtree is not None:
                            tree["children"][child.name] = subtree
            except PermissionError:
                tree["error"] = "Permission denied"
            
            return tree
        
        return build_tree(self.project_root)
    
    def _get_dependencies(self) -> List[Dict]:
        """Extract project dependencies."""
        dependencies = []
        
        # Python: requirements.txt
        req_file = self.project_root / "requirements.txt"
        if req_file.exists():
            dependencies.extend(self._parse_requirements_txt(req_file))
        
        # Python: setup.py
        setup_py = self.project_root / "setup.py"
        if setup_py.exists():
            dependencies.extend(self._parse_setup_py(setup_py))
        
        # Python: pyproject.toml
        pyproject = self.project_root / "pyproject.toml"
        if pyproject.exists():
            dependencies.extend(self._parse_pyproject_toml(pyproject))
        
        # Node.js: package.json
        package_json = self.project_root / "package.json"
        if package_json.exists():
            dependencies.extend(self._parse_package_json(package_json, "dependencies"))
        
        # Deduplicate
        seen = set()
        unique_deps = []
        for dep in dependencies:
            key = (dep["name"], dep.get("source"))
            if key not in seen:
                seen.add(key)
                unique_deps.append(dep)
        
        return unique_deps
    
    def _get_dev_dependencies(self) -> List[Dict]:
        """Extract development dependencies."""
        dev_deps = []
        
        # Python: dev_requirements.txt, requirements-dev.txt
        for filename in ["dev_requirements.txt", "requirements-dev.txt", "requirements_dev.txt"]:
            dev_req = self.project_root / filename
            if dev_req.exists():
                dev_deps.extend(self._parse_requirements_txt(dev_req))
        
        # Node.js: package.json devDependencies
        package_json = self.project_root / "package.json"
        if package_json.exists():
            dev_deps.extend(self._parse_package_json(package_json, "devDependencies"))
        
        return dev_deps
    
    def _parse_requirements_txt(self, file_path: Path) -> List[Dict]:
        """Parse Python requirements.txt file."""
        deps = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    
                    # Handle -r includes
                    if line.startswith('-r'):
                        continue
                    
                    # Extract package name and version
                    # Handle: package, package==1.0, package>=1.0, etc.
                    match = re.match(r'^([a-zA-Z0-9_-]+)([><=!]=?.*)?', line)
                    if match:
                        name = match.group(1)
                        version_spec = match.group(2).strip() if match.group(2) else None
                        
                        deps.append({
                            "name": name,
                            "version": version_spec,
                            "source": file_path.name,
                            "type": "python"
                        })
        except:
            pass
        
        return deps
    
    def _parse_setup_py(self, file_path: Path) -> List[Dict]:
        """Parse setup.py for dependencies."""
        deps = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # Extract install_requires
                match = re.search(r'install_requires\s*=\s*\[(.*?)\]', content, re.DOTALL)
                if match:
                    requires_str = match.group(1)
                    
                    # Extract each package
                    packages = re.findall(r'["\']([^"\']+)["\']', requires_str)
                    for pkg in packages:
                        pkg_match = re.match(r'^([a-zA-Z0-9_-]+)([><=!]=?.*)?', pkg)
                        if pkg_match:
                            deps.append({
                                "name": pkg_match.group(1),
                                "version": pkg_match.group(2).strip() if pkg_match.group(2) else None,
                                "source": "setup.py",
                                "type": "python"
                            })
        except:
            pass
        
        return deps
    
    def _parse_pyproject_toml(self, file_path: Path) -> List[Dict]:
        """Parse pyproject.toml for dependencies."""
        deps = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # Simple regex-based parsing (not full TOML parser)
                # Look for dependencies section
                in_dependencies = False
                for line in content.split('\n'):
                    line = line.strip()
                    
                    if line.startswith('[') and 'dependencies' in line.lower():
                        in_dependencies = True
                        continue
                    
                    if in_dependencies and line.startswith('['):
                        in_dependencies = False
                    
                    if in_dependencies and '=' in line:
                        match = re.match(r'([a-zA-Z0-9_-]+)\s*=\s*["\']([^"\']+)["\']', line)
                        if match:
                            deps.append({
                                "name": match.group(1),
                                "version": match.group(2),
                                "source": "pyproject.toml",
                                "type": "python"
                            })
        except:
            pass
        
        return deps
    
    def _parse_package_json(self, file_path: Path, dep_type: str = "dependencies") -> List[Dict]:
        """Parse package.json for dependencies."""
        deps = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                data = json.load(f)
                
                if dep_type in data:
                    for name, version in data[dep_type].items():
                        deps.append({
                            "name": name,
                            "version": version,
                            "source": "package.json",
                            "type": "javascript"
                        })
        except:
            pass
        
        return deps
    
    def _find_config_files(self) -> List[str]:
        """Find configuration files in the project."""
        config_patterns = [
            # Python
            'setup.py', 'setup.cfg', 'pyproject.toml', 'requirements.txt',
            'pytest.ini', 'tox.ini', 'mypy.ini', '.flake8', '.pylintrc',
            
            # JavaScript/Node
            'package.json', 'tsconfig.json', 'webpack.config.js',
            '.eslintrc', '.eslintrc.json', '.prettierrc', '.babelrc',
            
            # General
            '.gitignore', '.dockerignore', '.editorconfig',
            'Dockerfile', 'docker-compose.yml', 'Makefile',
            '.env.example', 'README.md', 'LICENSE'
        ]
        
        found_configs = []
        
        for pattern in config_patterns:
            config_file = self.project_root / pattern
            if config_file.exists():
                found_configs.append(pattern)
        
        return found_configs
    
    def _extract_documentation(self) -> Dict[str, str]:
        """Extract key documentation content."""
        docs = {}
        
        # README
        for readme_name in ['README.md', 'README.rst', 'README.txt', 'README']:
            readme = self.project_root / readme_name
            if readme.exists():
                try:
                    with open(readme, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        # Store first 1000 chars as summary
                        docs['readme'] = content[:1000] + ("..." if len(content) > 1000 else "")
                        docs['readme_file'] = readme_name
                except:
                    pass
                break
        
        # CHANGELOG
        for changelog_name in ['CHANGELOG.md', 'CHANGELOG.rst', 'CHANGELOG.txt', 'HISTORY.md']:
            changelog = self.project_root / changelog_name
            if changelog.exists():
                try:
                    with open(changelog, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        # Get latest entries (first 500 chars)
                        docs['changelog'] = content[:500] + ("..." if len(content) > 500 else "")
                except:
                    pass
                break
        
        # LICENSE
        for license_name in ['LICENSE', 'LICENSE.txt', 'LICENSE.md']:
            license_file = self.project_root / license_name
            if license_file.exists():
                try:
                    with open(license_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        # Try to detect license type
                        if 'MIT' in content:
                            docs['license'] = 'MIT'
                        elif 'Apache' in content:
                            docs['license'] = 'Apache'
                        elif 'GPL' in content:
                            docs['license'] = 'GPL'
                        else:
                            docs['license'] = 'Custom/Other'
                except:
                    pass
                break
        
        return docs
    
    def _detect_project_type(self) -> List[str]:
        """Detect what type of project this is."""
        project_types = []
        
        # Python
        if (self.project_root / "setup.py").exists() or \
           (self.project_root / "pyproject.toml").exists() or \
           (self.project_root / "requirements.txt").exists():
            project_types.append("python")
        
        # JavaScript/TypeScript
        if (self.project_root / "package.json").exists():
            project_types.append("javascript")
            
            # Check for specific frameworks
            package_json = self.project_root / "package.json"
            try:
                with open(package_json, 'r') as f:
                    data = json.load(f)
                    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                    
                    if "react" in deps:
                        project_types.append("react")
                    if "vue" in deps:
                        project_types.append("vue")
                    if "next" in deps:
                        project_types.append("nextjs")
                    if "express" in deps:
                        project_types.append("express")
            except:
                pass
        
        # TypeScript
        if (self.project_root / "tsconfig.json").exists():
            project_types.append("typescript")
        
        # Docker
        if (self.project_root / "Dockerfile").exists():
            project_types.append("docker")
        
        # Git repository
        if (self.project_root / ".git").exists():
            project_types.append("git")
        
        return project_types if project_types else ["unknown"]
    
    def _get_project_statistics(self) -> Dict[str, int]:
        """Get project statistics (file counts, line counts, etc.)."""
        stats = {
            "total_files": 0,
            "total_directories": 0,
            "python_files": 0,
            "javascript_files": 0,
            "total_lines": 0
        }
        
        # Count files
        for path in self.project_root.rglob('*'):
            # Skip ignored directories
            if any(part.startswith('.') or part in {'__pycache__', 'node_modules', 'venv'}
                  for part in path.parts):
                continue
            
            if path.is_file():
                stats["total_files"] += 1
                
                if path.suffix == '.py':
                    stats["python_files"] += 1
                    try:
                        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                            stats["total_lines"] += len(f.readlines())
                    except:
                        pass
                
                elif path.suffix in {'.js', '.jsx', '.ts', '.tsx'}:
                    stats["javascript_files"] += 1
            
            elif path.is_dir():
                stats["total_directories"] += 1
        
        return stats
    
    def build_module_graph(self, ast_parser) -> Dict[str, List[str]]:
        """
        Build a graph of which files import which.
        
        Args:
            ast_parser: ASTParser instance with parsed files
            
        Returns:
            Dictionary mapping file_path -> [list of imported files]
        """
        graph = {}
        
        for file_path, structure in ast_parser.parsed_files.items():
            imports = structure.get("imports", [])
            imported_files = []
            
            for imp in imports:
                # Try to resolve import to actual file path
                resolved = self._resolve_import_path(file_path, imp)
                if resolved:
                    imported_files.append(resolved)
            
            graph[file_path] = imported_files
        
        return graph
    
    def _resolve_import_path(self, source_file: str, import_info: Dict) -> Optional[str]:
        """
        Resolve an import to an actual file path.
        
        Returns relative path from project root, or None if can't resolve.
        """
        import_type = import_info.get("type")
        module = import_info.get("module", "")
        
        if not module:
            return None
        
        # Convert module name to file path
        module_path = module.replace('.', '/')
        
        # Try various locations
        candidates = [
            f"{module_path}.py",
            f"{module_path}/__init__.py",
            str(Path(source_file).parent / f"{module}.py")
        ]
        
        for candidate in candidates:
            if (self.project_root / candidate).exists():
                return candidate
        
        return None
    
    def get_summary(self) -> str:
        """Get a human-readable summary of the project."""
        context = self.get_project_context()
        
        summary_parts = [
            f"Project: {context['project_name']}",
            f"Type: {', '.join(context['project_type'])}",
        ]
        
        metadata = context.get('project_metadata', {})
        if 'version' in metadata:
            summary_parts.append(f"Version: {metadata['version']}")
        
        stats = context.get('statistics', {})
        if stats:
            summary_parts.append(f"Files: {stats.get('total_files', 0)} ({stats.get('python_files', 0)} Python)")
            summary_parts.append(f"Lines of code: {stats.get('total_lines', 0)}")
        
        deps = context.get('dependencies', [])
        if deps:
            summary_parts.append(f"Dependencies: {len(deps)}")
        
        return "\n".join(summary_parts)
