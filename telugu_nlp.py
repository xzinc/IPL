#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Telugu NLP Module for IPL Telegram Bot
--------------------------------------
This module provides Telugu language processing capabilities for the IPL Telegram Bot.
"""

import os
import json
import logging
import kagglehub
import pandas as pd
from pathlib import Path
import nltk
from nltk.tokenize import word_tokenize
import pickle

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TeluguNLP:
    """Telugu Natural Language Processing for IPL Telegram Bot"""
    
    def __init__(self, data_dir=None):
        """Initialize Telugu NLP module"""
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), 'data', 'telugu_nlp')
        self.dataset_path = None
        self.vocab = None
        self.translations = {}
        self.ipl_terms = {}
        self.model_loaded = False
        
        # Create data directory if it doesn't exist
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Download NLTK data if not already downloaded
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')
    
    def download_dataset(self, force_download=False):
        """Download Telugu NLP dataset from Kaggle"""
        dataset_cache = os.path.join(self.data_dir, 'dataset_path.txt')
        
        # Check if dataset is already downloaded
        if os.path.exists(dataset_cache) and not force_download:
            with open(dataset_cache, 'r', encoding='utf-8') as f:
                self.dataset_path = f.read().strip()
                if os.path.exists(self.dataset_path):
                    logger.info(f"Using cached Telugu NLP dataset at: {self.dataset_path}")
                    return self.dataset_path
        
        # Download dataset
        logger.info("Downloading Telugu NLP dataset from Kaggle...")
        try:
            self.dataset_path = kagglehub.dataset_download("sudalairajkumar/telugu-nlp")
            logger.info(f"Telugu NLP dataset downloaded to: {self.dataset_path}")
            
            # Save dataset path to cache
            with open(dataset_cache, 'w', encoding='utf-8') as f:
                f.write(self.dataset_path)
            
            return self.dataset_path
        except Exception as e:
            logger.error(f"Error downloading Telugu NLP dataset: {e}")
            raise
    
    def load_dataset(self):
        """Load Telugu NLP dataset"""
        if not self.dataset_path:
            self.download_dataset()
        
        # Load vocabulary
        vocab_path = os.path.join(self.dataset_path, 'telugu_words.txt')
        if os.path.exists(vocab_path):
            with open(vocab_path, 'r', encoding='utf-8') as f:
                self.vocab = set(line.strip() for line in f)
            logger.info(f"Loaded {len(self.vocab)} Telugu words")
        
        # Load Telugu-English translations
        translation_path = os.path.join(self.dataset_path, 'telugu_translations.csv')
        if os.path.exists(translation_path):
            try:
                df = pd.read_csv(translation_path)
                for _, row in df.iterrows():
                    if 'telugu' in row and 'english' in row:
                        self.translations[row['telugu']] = row['english']
                logger.info(f"Loaded {len(self.translations)} Telugu-English translations")
            except Exception as e:
                logger.error(f"Error loading translations: {e}")
        
        # Initialize IPL-specific Telugu terms
        self.initialize_ipl_terms()
        
        self.model_loaded = True
        return True
    
    def initialize_ipl_terms(self):
        """Initialize IPL-specific Telugu terms"""
        # Common IPL terms in Telugu
        self.ipl_terms = {
            "క్రికెట్": "cricket",
            "ఐపీఎల్": "IPL",
            "జట్టు": "team",
            "ఆటగాడు": "player",
            "పోటీ": "match",
            "విజేత": "winner",
            "ఓటమి": "defeat",
            "పరుగులు": "runs",
            "వికెట్లు": "wickets",
            "బ్యాట్సుమెన్": "batsman",
            "బౌలర్": "bowler",
            "కెప్టెన్": "captain",
            "కోచ్": "coach",
            "స్టేడియం": "stadium",
            "పాయింట్లు": "points",
            "ఫైనల్": "final",
            "ప్లేఆఫ్స్": "playoffs",
            "ఛాంపియన్": "champion",
            "ట్రోఫీ": "trophy",
            "ఆటగాళ్ళు": "players",
            "సీజన్": "season",
            "టోర్నమెంట్": "tournament",
            "ఆడుతున్నారు": "playing",
            "గెలుస్తారు": "will win",
            "ఓడిపోతారు": "will lose",
            "స్కోరు": "score",
            "ఓవర్లు": "overs",
            "బంతులు": "balls",
            "బౌండరీలు": "boundaries",
            "సిక్సర్లు": "sixes",
            "ఫోర్లు": "fours"
        }
        
        # Add team names in Telugu
        team_names = {
            "ముంబై ఇండియన్స్": "Mumbai Indians",
            "చెన్నై సూపర్ కింగ్స్": "Chennai Super Kings",
            "రాయల్ ఛాలెంజర్స్ బెంగళూరు": "Royal Challengers Bangalore",
            "కోల్కతా నైట్ రైడర్స్": "Kolkata Knight Riders",
            "దిల్లీ క్యాపిటల్స్": "Delhi Capitals",
            "సన్‌రైజర్స్ హైదరాబాద్": "Sunrisers Hyderabad",
            "రాజస్థాన్ రాయల్స్": "Rajasthan Royals",
            "పంజాబ్ కింగ్స్": "Punjab Kings",
            "గుజరాత్ టైటాన్స్": "Gujarat Titans",
            "లక్నో సూపర్ జెయింట్స్": "Lucknow Super Giants"
        }
        
        # Update IPL terms with team names
        self.ipl_terms.update(team_names)
        
        # Save IPL terms to file
        ipl_terms_path = os.path.join(self.data_dir, 'ipl_terms.json')
        with open(ipl_terms_path, 'w', encoding='utf-8') as f:
            json.dump(self.ipl_terms, f, ensure_ascii=False, indent=4)
        
        logger.info(f"Initialized {len(self.ipl_terms)} IPL-specific Telugu terms")
    
    def detect_language(self, text):
        """Detect if text contains Telugu"""
        if not text:
            return False
        
        # Check for Telugu Unicode range (0C00-0C7F)
        for char in text:
            if '\u0C00' <= char <= '\u0C7F':
                return True
        
        return False
    
    def tokenize(self, text):
        """Tokenize Telugu text"""
        return word_tokenize(text)
    
    def translate_to_english(self, text):
        """Translate Telugu text to English"""
        if not self.model_loaded:
            self.load_dataset()
        
        if not self.detect_language(text):
            return text
        
        # Tokenize the text
        tokens = self.tokenize(text)
        
        # Translate each token
        translated_tokens = []
        for token in tokens:
            # Check if token is in IPL terms
            if token in self.ipl_terms:
                translated_tokens.append(self.ipl_terms[token])
            # Check if token is in general translations
            elif token in self.translations:
                translated_tokens.append(self.translations[token])
            # Keep the original token if not found
            else:
                translated_tokens.append(token)
        
        # Join the translated tokens
        translated_text = ' '.join(translated_tokens)
        
        return translated_text
    
    def translate_to_telugu(self, text, ipl_context=True):
        """Translate English text to Telugu (simple version)"""
        if not self.model_loaded:
            self.load_dataset()
        
        # Tokenize the text
        tokens = self.tokenize(text.lower())
        
        # Create reverse mappings
        reverse_translations = {v: k for k, v in self.translations.items()}
        reverse_ipl_terms = {v.lower(): k for k, v in self.ipl_terms.items()}
        
        # Translate each token
        translated_tokens = []
        for token in tokens:
            # Check if token is in IPL terms (if ipl_context is True)
            if ipl_context and token.lower() in reverse_ipl_terms:
                translated_tokens.append(reverse_ipl_terms[token.lower()])
            # Check if token is in general translations
            elif token.lower() in reverse_translations:
                translated_tokens.append(reverse_translations[token.lower()])
            # Keep the original token if not found
            else:
                translated_tokens.append(token)
        
        # Join the translated tokens
        translated_text = ' '.join(translated_tokens)
        
        return translated_text
    
    def save_model(self):
        """Save the NLP model to disk"""
        if not self.model_loaded:
            logger.warning("No model to save")
            return False
        
        model_path = os.path.join(self.data_dir, 'telugu_nlp_model.pkl')
        model_data = {
            'vocab': self.vocab,
            'translations': self.translations,
            'ipl_terms': self.ipl_terms
        }
        
        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info(f"Telugu NLP model saved to: {model_path}")
        return True
    
    def load_model(self):
        """Load the NLP model from disk"""
        model_path = os.path.join(self.data_dir, 'telugu_nlp_model.pkl')
        
        if os.path.exists(model_path):
            try:
                with open(model_path, 'rb') as f:
                    model_data = pickle.load(f)
                
                self.vocab = model_data.get('vocab')
                self.translations = model_data.get('translations', {})
                self.ipl_terms = model_data.get('ipl_terms', {})
                self.model_loaded = True
                
                logger.info(f"Telugu NLP model loaded from: {model_path}")
                return True
            except Exception as e:
                logger.error(f"Error loading Telugu NLP model: {e}")
        
        # If model doesn't exist or loading failed, download and load the dataset
        return self.load_dataset()

# Example usage
if __name__ == "__main__":
    telugu_nlp = TeluguNLP()
    telugu_nlp.download_dataset()
    telugu_nlp.load_dataset()
    
    # Test detection
    test_text = "ఐపీఎల్ క్రికెట్ టోర్నమెంట్"
    print(f"Detecting Telugu in '{test_text}': {telugu_nlp.detect_language(test_text)}")
    
    # Test translation
    print(f"Translating '{test_text}' to English: {telugu_nlp.translate_to_english(test_text)}")
    
    # Test reverse translation
    english_text = "Mumbai Indians will win IPL this season"
    print(f"Translating '{english_text}' to Telugu: {telugu_nlp.translate_to_telugu(english_text)}")
    
    # Save the model
    telugu_nlp.save_model()
