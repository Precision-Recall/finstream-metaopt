"""
Firebase Firestore REST API Client.

Wrapper around Google Firestore REST API (no service account required).
All read/write operations to Firestore are centralized here.

Configuration:
  Load Firebase project settings from .env using python-dotenv.

Firestore Rules (must be set in Firebase Console):
  rules_version = '2';
  service cloud.firestore {
    match /databases/{database}/documents {
      match /{document=**} {
        allow read, write: if true;
      }
    }
  }
"""

import os
import json
import logging
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _to_firestore_value(value: Any) -> Dict[str, Any]:
    """
    Convert Python value to Firestore REST API format.
    
    Examples:
        str   → {"stringValue": value}
        int   → {"integerValue": str(value)}
        float → {"doubleValue": value}
        bool  → {"booleanValue": value}
        list  → {"arrayValue": {"values": [...]}}
        dict  → {"mapValue": {"fields": {...}}}
        None  → {"nullValue": None}
    """
    if value is None:
        return {"nullValue": None}
    elif isinstance(value, bool):
        return {"booleanValue": value}
    elif isinstance(value, int):
        return {"integerValue": str(value)}
    elif isinstance(value, float):
        return {"doubleValue": value}
    elif isinstance(value, str):
        return {"stringValue": value}
    elif isinstance(value, list):
        return {
            "arrayValue": {
                "values": [_to_firestore_value(item) for item in value]
            }
        }
    elif isinstance(value, dict):
        return {
            "mapValue": {
                "fields": {
                    key: _to_firestore_value(val)
                    for key, val in value.items()
                }
            }
        }
    else:
        # Fallback: convert to string
        return {"stringValue": str(value)}


def _from_firestore_value(value_dict: Dict[str, Any]) -> Any:
    """
    Convert Firestore REST API value back to Python.
    Inverse of _to_firestore_value().
    """
    if not isinstance(value_dict, dict):
        return value_dict
    
    if "nullValue" in value_dict:
        return None
    elif "booleanValue" in value_dict:
        return value_dict["booleanValue"]
    elif "integerValue" in value_dict:
        return int(value_dict["integerValue"])
    elif "doubleValue" in value_dict:
        return value_dict["doubleValue"]
    elif "stringValue" in value_dict:
        return value_dict["stringValue"]
    elif "arrayValue" in value_dict:
        values = value_dict["arrayValue"].get("values", [])
        return [_from_firestore_value(v) for v in values]
    elif "mapValue" in value_dict:
        fields = value_dict["mapValue"].get("fields", {})
        return {key: _from_firestore_value(val) for key, val in fields.items()}
    else:
        return value_dict


class FirebaseClient:
    """
    Firestore REST API client for reading and writing documents.
    """

    def __init__(self):
        """Initialize Firebase client with credentials from .env."""
        self.project_id = os.getenv('FIREBASE_PROJECT_ID')
        self.api_key = os.getenv('FIREBASE_API_KEY')
        
        if not self.project_id or not self.api_key:
            logger.error("Missing FIREBASE_PROJECT_ID or FIREBASE_API_KEY in .env")
            raise ValueError("Firebase credentials not configured")
        
        self.base_url = (
            f"https://firestore.googleapis.com/v1/projects/{self.project_id}/"
            f"databases/(default)/documents"
        )
        self.session = requests.Session()
        logger.info(f"Firebase client initialized for project: {self.project_id}")

    def _get_params(self) -> Dict[str, str]:
        """Return query parameters for all requests."""
        return {"key": self.api_key}

    def _build_url(self, collection: str, document: str = "") -> str:
        """Build full Firestore REST API URL."""
        url = f"{self.base_url}/{collection}"
        if document:
            url += f"/{document}"
        return url

    def _build_fields(self, data: dict) -> dict:
        """Convert dict values to Firestore format."""
        return {k: _to_firestore_value(v) for k, v in data.items()}

    def save_document(self, collection: str, doc_id: str, data: dict) -> bool:
        """
        Save or overwrite a document by collection + doc_id.
        Generic method for any collection/document pair.
        
        Args:
            collection: collection name
            doc_id: document ID
            data: dict of data to save
        
        Returns:
            True if successful, False otherwise.
        """
        try:
            url = f"{self.base_url}/{collection}/{doc_id}"
            fields = self._build_fields(data)
            response = self.session.patch(
                url,
                json={"fields": fields},
                params=self._get_params()
            )
            
            if response.status_code not in (200, 201):
                logger.error(f"Failed to save {collection}/{doc_id}: {response.text}")
                return False
            
            logger.info(f"Saved {collection}/{doc_id}")
            return True
        
        except Exception as e:
            logger.error(f"save_document error: {e}")
            return False

    def save_prediction(self, prediction_dict: Dict[str, Any]) -> bool:
        """
        Save a prediction to Firestore.
        
        Args:
            prediction_dict: dict with keys like 'date', 'prediction', 'probability', etc.
        
        Returns:
            True if successful, False otherwise.
        """
        try:
            date = prediction_dict.get('date')
            if not date:
                logger.error("Prediction dict missing 'date' field")
                return False
            
            logger.info(f"Saving prediction for {date}...")
            
            # Convert to Firestore format
            fields = {
                key: _to_firestore_value(value)
                for key, value in prediction_dict.items()
            }
            
            logger.debug(f"Fields to save: {list(fields.keys())}")
            
            # Prepare request body
            body = {"fields": fields}
            
            # POST to Firestore (document ID is the date)
            url = self._build_url("predictions", date)
            logger.info(f"Making PATCH request to: {url}")
            
            response = self.session.patch(
                url,
                json=body,
                params=self._get_params(),
                timeout=10
            )
            
            logger.info(f"Firestore response status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                logger.info(f"✓ Saved prediction for {date}")
                return True
            else:
                logger.error(f"✗ Failed to save prediction: HTTP {response.status_code}")
                logger.error(f"  Response body: {response.text}")
                logger.error(f"  URL: {url}")
                logger.error(f"  Request body: {body}")
                return False
        
        except Exception as e:
            logger.error(f"✗ Exception saving prediction: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"  Traceback: {traceback.format_exc()}")
            return False

    def save_evaluation(self, evaluation_dict: Dict[str, Any]) -> bool:
        """
        Save evaluation and update corresponding prediction.
        
        Args:
            evaluation_dict: dict with 'date', 'truth', 'error', etc.
        
        Returns:
            True if successful, False otherwise.
        """
        try:
            date = evaluation_dict.get('date')
            if not date:
                logger.error("Evaluation dict missing 'date' field")
                return False
            
            # Save evaluation
            fields = {
                key: _to_firestore_value(value)
                for key, value in evaluation_dict.items()
            }
            
            body = {"fields": fields}
            url = self._build_url("evaluations", date)
            response = self.session.patch(
                url,
                json=body,
                params=self._get_params()
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"Failed to save evaluation: {response.status_code} {response.text}")
                return False
            
            # Update corresponding prediction to mark it resolved
            prediction_update = {
                "resolved": True,
                "truth": evaluation_dict['truth'],
                "error": evaluation_dict['error']
            }
            fields = {
                key: _to_firestore_value(value)
                for key, value in prediction_update.items()
            }
            
            body = {"fields": fields}
            url = self._build_url("predictions", date)
            response = self.session.patch(
                url,
                json=body,
                params=self._get_params()
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Saved evaluation for {date}")
                return True
            else:
                logger.error(f"Failed to update prediction: {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"Error saving evaluation: {e}")
            return False

    def save_drift_event(self, drift_dict: Dict[str, Any]) -> bool:
        """
        Save a drift event to Firestore.
        
        Args:
            drift_dict: dict with drift event details
        
        Returns:
            True if successful, False otherwise.
        """
        try:
            date = drift_dict.get('date')
            row_index = drift_dict.get('row_index', 0)
            if not date:
                logger.error("Drift dict missing 'date' field")
                return False
            
            # Use date + row_index as document ID
            doc_id = f"{date}_{row_index}"
            
            fields = {
                key: _to_firestore_value(value)
                for key, value in drift_dict.items()
            }
            
            body = {"fields": fields}
            url = self._build_url("drift_events", doc_id)
            response = self.session.patch(
                url,
                json=body,
                params=self._get_params()
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Saved drift event for {date}")
                return True
            else:
                logger.error(f"Failed to save drift event: {response.status_code} {response.text}")
                return False
        
        except Exception as e:
            logger.error(f"Error saving drift event: {e}")
            return False

    def update_model_state(self, state_dict: Dict[str, Any]) -> bool:
        """
        Update current model state in system collection.
        
        Args:
            state_dict: dict with active_features, ensemble_weights, council_weights, etc.
        
        Returns:
            True if successful, False otherwise.
        """
        try:
            logger.info("Updating model state...")
            
            fields = {
                key: _to_firestore_value(value)
                for key, value in state_dict.items()
            }
            
            body = {"fields": fields}
            url = self._build_url("system", "current")
            
            logger.info(f"Making PATCH request to: {url}")
            
            response = self.session.patch(
                url,
                json=body,
                params=self._get_params(),
                timeout=10
            )
            
            logger.info(f"Firestore response status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                logger.info("✓ Updated model state")
                return True
            else:
                logger.error(f"✗ Failed to update model state: HTTP {response.status_code}")
                logger.error(f"  Response body: {response.text}")
                return False
        
        except Exception as e:
            logger.error(f"✗ Exception updating model state: {type(e).__name__}: {e}")
            return False

    def get_model_state(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve current model state from Firestore.
        
        Returns:
            dict if found, None otherwise.
        """
        try:
            url = self._build_url("system", "current")
            logger.info(f"Getting model state from: {url}")
            
            response = self.session.get(
                url, 
                params=self._get_params(),
                timeout=10
            )
            
            logger.info(f"Firestore response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if "fields" in data:
                    state = {
                        key: _from_firestore_value(value)
                        for key, value in data["fields"].items()
                    }
                    logger.info("✓ Retrieved model state from Firestore")
                    return state
                else:
                    logger.warning("Model state document exists but has no fields")
                    return None
            elif response.status_code == 404:
                logger.info("Model state not found (first run)")
                return None
            else:
                logger.error(f"✗ Failed to get model state: HTTP {response.status_code}")
                logger.error(f"  Response body: {response.text}")
                return None
        
        except Exception as e:
            logger.error(f"✗ Exception retrieving model state: {type(e).__name__}: {e}")
            return None
            logger.error(f"Error retrieving model state: {e}")
            return None

    def get_unresolved_predictions(self) -> List[Dict[str, Any]]:
        """
        Get all unresolved predictions (resolved=False).
        
        Returns:
            list of prediction dicts, or empty list on error.
        """
        try:
            # Note: REST API doesn't support direct filtering easily
            # This is a simplified version — in production, use a backend function
            # or stream all and filter
            logger.warning("get_unresolved_predictions: Full implementation requires backend")
            return []
        
        except Exception as e:
            logger.error(f"Error getting unresolved predictions: {e}")
            return []

    def get_recent_predictions(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        Get the last n predictions ordered by date.
        
        Args:
            n: number of predictions to retrieve
        
        Returns:
            list of prediction dicts, or empty list on error.
        """
        try:
            # Note: REST API requires full implementation in backend
            # This is a placeholder
            logger.warning("get_recent_predictions: Full implementation requires backend")
            return []
        
        except Exception as e:
            logger.error(f"Error getting recent predictions: {e}")
            return []

    def get_prediction_by_date(self, date: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific prediction by date.
        
        Args:
            date: date string (YYYY-MM-DD)
        
        Returns:
            prediction dict if found, None otherwise.
        """
        try:
            url = self._build_url("predictions", date)
            logger.info(f"Retrieving prediction from: {url}")
            
            response = self.session.get(
                url, 
                params=self._get_params(),
                timeout=10
            )
            
            logger.info(f"Firestore response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if "fields" in data:
                    prediction = {
                        key: _from_firestore_value(value)
                        for key, value in data["fields"].items()
                    }
                    logger.info(f"✓ Retrieved prediction for {date}")
                    return prediction
            elif response.status_code == 404:
                logger.info(f"Prediction not found for {date}")
                return None
            else:
                logger.error(f"✗ Failed to get prediction: HTTP {response.status_code}")
                logger.error(f"  Response body: {response.text}")
                return None
        
        except Exception as e:
            logger.error(f"✗ Exception retrieving prediction: {type(e).__name__}: {e}")
            return None


if __name__ == '__main__':
    # Test Firebase connectivity
    try:
        client = FirebaseClient()
        print(f"✓ Firebase client initialized")
        print(f"  Project: {client.project_id}")
        print(f"  Base URL: {client.base_url}")
        
        # Try to get model state (might not exist yet)
        state = client.get_model_state()
        print(f"✓ Firebase connectivity verified")
    except Exception as e:
        print(f"✗ Firebase initialization failed: {e}")
