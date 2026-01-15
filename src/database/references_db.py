"""
Creative References Database using ChromaDB

Stores articles, designs, fonts, styles for the creative system.
Supports semantic search to find relevant references.
"""

import chromadb
from chromadb.config import Settings
import uuid
from datetime import datetime
from typing import Optional
from ..config import config


class ReferencesDB:
    """Database for creative references (articles, designs, fonts, etc.)"""
    
    # Categories that influence ALL outputs
    GENERAL_CATEGORIES = [
        "copywriting",      # Writing style references
        "design",           # Visual design references
        "fonts",            # Typography
        "colors",           # Color palettes
        "styles",           # General style guides
        "landing_pages",    # Landing page examples
        "thumbnails",       # Article/video thumbnails
        "logos",            # Logo designs
        "twitter",          # Tweet styles
    ]
    
    def __init__(self, persist_dir: str = None):
        self.persist_dir = persist_dir or config.CHROMA_PERSIST_DIR
        self.client = chromadb.PersistentClient(
            path=f"{self.persist_dir}/references",
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name="creative_references",
            metadata={"description": "Creative references for content production"}
        )
    
    def add_reference(
        self,
        content: str,
        source_url: str = None,
        category: str = "uncategorized",
        project: str = None,
        title: str = None,
        content_type: str = "article",  # article, image, tweet, design
        tags: list[str] = None
    ) -> str:
        """
        Add a new reference to the database.
        
        Args:
            content: The actual content (text, or description for images)
            source_url: Original URL where this was found
            category: One of GENERAL_CATEGORIES or custom
            project: If set, only used for this specific project
            title: Optional title
            content_type: Type of content
            tags: Additional tags for filtering
            
        Returns:
            The ID of the created reference
        """
        ref_id = str(uuid.uuid4())
        
        metadata = {
            "source_url": source_url or "",
            "category": category,
            "project": project or "",  # Empty string = general reference
            "title": title or "",
            "content_type": content_type,
            "tags": ",".join(tags) if tags else "",
            "created_at": datetime.now().isoformat(),
        }
        
        self.collection.add(
            ids=[ref_id],
            documents=[content],
            metadatas=[metadata]
        )
        
        return ref_id
    
    def search(
        self,
        query: str,
        category: str = None,
        project: str = None,
        content_type: str = None,
        limit: int = 10,
        include_project_refs: bool = False
    ) -> list[dict]:
        """
        Semantic search for references.
        
        Args:
            query: What to search for
            category: Filter by category
            project: Filter by project (None = general only)
            content_type: Filter by content type
            limit: Max results
            include_project_refs: If True, include project-specific refs too
            
        Returns:
            List of matching references with metadata
        """
        where_filters = []
        
        if category:
            where_filters.append({"category": category})
        
        if content_type:
            where_filters.append({"content_type": content_type})
        
        # By default, only return general references (no project)
        if not include_project_refs and not project:
            where_filters.append({"project": ""})
        elif project:
            # Return both general AND this specific project's refs
            where_filters.append({
                "$or": [
                    {"project": ""},
                    {"project": project}
                ]
            })
        
        where = None
        if len(where_filters) == 1:
            where = where_filters[0]
        elif len(where_filters) > 1:
            where = {"$and": where_filters}
        
        results = self.collection.query(
            query_texts=[query],
            n_results=limit,
            where=where if where_filters else None
        )
        
        # Format results nicely
        formatted = []
        if results["ids"] and results["ids"][0]:
            for i, ref_id in enumerate(results["ids"][0]):
                formatted.append({
                    "id": ref_id,
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None
                })
        
        return formatted
    
    def get_by_id(self, ref_id: str) -> Optional[dict]:
        """Get a specific reference by ID"""
        result = self.collection.get(ids=[ref_id])
        if result["ids"]:
            return {
                "id": result["ids"][0],
                "content": result["documents"][0] if result["documents"] else "",
                "metadata": result["metadatas"][0] if result["metadatas"] else {}
            }
        return None
    
    def update(self, ref_id: str, **kwargs) -> bool:
        """Update a reference's metadata or content"""
        existing = self.get_by_id(ref_id)
        if not existing:
            return False
        
        new_metadata = existing["metadata"].copy()
        new_content = existing["content"]
        
        if "content" in kwargs:
            new_content = kwargs.pop("content")
        
        # Update metadata fields
        for key, value in kwargs.items():
            if key in new_metadata:
                new_metadata[key] = value if not isinstance(value, list) else ",".join(value)
        
        self.collection.update(
            ids=[ref_id],
            documents=[new_content],
            metadatas=[new_metadata]
        )
        return True
    
    def delete(self, ref_id: str) -> bool:
        """Delete a reference"""
        try:
            self.collection.delete(ids=[ref_id])
            return True
        except Exception:
            return False
    
    def list_all(
        self,
        category: str = None,
        project: str = None,
        limit: int = 100
    ) -> list[dict]:
        """List all references, optionally filtered"""
        where = None
        if category and project:
            where = {"$and": [{"category": category}, {"project": project}]}
        elif category:
            where = {"category": category}
        elif project:
            where = {"project": project}
        
        results = self.collection.get(
            where=where,
            limit=limit
        )
        
        formatted = []
        if results["ids"]:
            for i, ref_id in enumerate(results["ids"]):
                formatted.append({
                    "id": ref_id,
                    "content": results["documents"][i][:200] + "..." if len(results["documents"][i]) > 200 else results["documents"][i],
                    "metadata": results["metadatas"][i]
                })
        
        return formatted
    
    def get_categories(self) -> list[str]:
        """Get list of all categories in use"""
        all_refs = self.collection.get()
        categories = set()
        if all_refs["metadatas"]:
            for meta in all_refs["metadatas"]:
                if meta.get("category"):
                    categories.add(meta["category"])
        return sorted(list(categories))
    
    def get_projects(self) -> list[str]:
        """Get list of all projects"""
        all_refs = self.collection.get()
        projects = set()
        if all_refs["metadatas"]:
            for meta in all_refs["metadatas"]:
                if meta.get("project"):
                    projects.add(meta["project"])
        return sorted(list(projects))


