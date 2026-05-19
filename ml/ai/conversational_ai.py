"""
Conversational AI Module
Handles AI-powered character interactions using LLMs
"""
import os
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger


@dataclass
class Message:
    """Single conversation message"""
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CharacterPersonality:
    """Character personality and background"""
    name: str
    age: Optional[int] = None
    background: str = ""
    traits: List[str] = field(default_factory=list)
    speaking_style: str = "casual"
    interests: List[str] = field(default_factory=list)
    relationships: Dict[str, str] = field(default_factory=dict)


class ConversationalAI:
    """
    AI-powered conversational system for virtual characters
    """
    
    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4-turbo-preview",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key or os.getenv(f"{provider.upper()}_API_KEY")
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Initialize client
        if provider == "openai":
            self._init_openai()
        elif provider == "anthropic":
            self._init_anthropic()
        else:
            raise ValueError(f"Unknown provider: {provider}")
        
        logger.info(f"Conversational AI initialized with {provider}/{model}")
    
    def _init_openai(self):
        """Initialize OpenAI client"""
        try:
            from openai import OpenAI
            
            self.client = OpenAI(api_key=self.api_key)
            logger.info("OpenAI client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI: {e}")
            raise
    
    def _init_anthropic(self):
        """Initialize Anthropic client"""
        try:
            from anthropic import Anthropic
            
            self.client = Anthropic(api_key=self.api_key)
            logger.info("Anthropic client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic: {e}")
            raise
    
    def create_system_prompt(
        self,
        personality: CharacterPersonality,
        context: Optional[str] = None
    ) -> str:
        """
        Create system prompt from character personality
        """
        prompt_parts = [
            f"You are {personality.name}, a virtual character in an immersive VR experience."
        ]
        
        if personality.age:
            prompt_parts.append(f"You are {personality.age} years old.")
        
        if personality.background:
            prompt_parts.append(f"Background: {personality.background}")
        
        if personality.traits:
            traits_str = ", ".join(personality.traits)
            prompt_parts.append(f"Your personality traits: {traits_str}")
        
        if personality.speaking_style:
            prompt_parts.append(f"Speaking style: {personality.speaking_style}")
        
        if personality.interests:
            interests_str = ", ".join(personality.interests)
            prompt_parts.append(f"Your interests: {interests_str}")
        
        if personality.relationships:
            rel_str = ", ".join([f"{k}: {v}" for k, v in personality.relationships.items()])
            prompt_parts.append(f"Relationships: {rel_str}")
        
        prompt_parts.extend([
            "\nYou should:",
            "- Stay in character at all times",
            "- Respond naturally and conversationally",
            "- Show emotions and personality",
            "- Reference your background and experiences",
            "- Be engaging and interactive",
            "- Keep responses concise (2-3 sentences typically)"
        ])
        
        if context:
            prompt_parts.append(f"\nCurrent context: {context}")
        
        return "\n".join(prompt_parts)
    
    def chat(
        self,
        message: str,
        personality: CharacterPersonality,
        conversation_history: List[Message],
        context: Optional[str] = None
    ) -> str:
        """
        Generate AI response to user message
        """
        # Create system prompt
        system_prompt = self.create_system_prompt(personality, context)
        
        # Prepare messages
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history (last 10 messages)
        for msg in conversation_history[-10:]:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        # Add current message
        messages.append({
            "role": "user",
            "content": message
        })
        
        # Generate response
        if self.provider == "openai":
            response = self._chat_openai(messages)
        elif self.provider == "anthropic":
            response = self._chat_anthropic(messages)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
        
        logger.info(f"Generated response for {personality.name}")
        
        return response
    
    def _chat_openai(self, messages: List[Dict]) -> str:
        """Generate response using OpenAI"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI chat failed: {e}")
            raise
    
    def _chat_anthropic(self, messages: List[Dict]) -> str:
        """Generate response using Anthropic"""
        try:
            # Extract system message
            system_msg = next((m['content'] for m in messages if m['role'] == 'system'), "")
            
            # Filter out system messages for Anthropic
            user_messages = [m for m in messages if m['role'] != 'system']
            
            response = self.client.messages.create(
                model=self.model,
                system=system_msg,
                messages=user_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic chat failed: {e}")
            raise
    
    def generate_contextual_response(
        self,
        user_action: str,
        personality: CharacterPersonality,
        scene_context: Dict
    ) -> str:
        """
        Generate response based on user action and scene context
        """
        context_parts = []
        
        if "location" in scene_context:
            context_parts.append(f"Location: {scene_context['location']}")
        
        if "time" in scene_context:
            context_parts.append(f"Time: {scene_context['time']}")
        
        if "other_characters" in scene_context:
            others = ", ".join(scene_context['other_characters'])
            context_parts.append(f"Others present: {others}")
        
        if "activity" in scene_context:
            context_parts.append(f"Current activity: {scene_context['activity']}")
        
        context = " | ".join(context_parts)
        
        prompt = f"The user {user_action}. How do you respond?"
        
        return self.chat(
            prompt,
            personality,
            [],
            context
        )
    
    def generate_emotion_response(
        self,
        emotion: str,
        intensity: float,
        personality: CharacterPersonality
    ) -> str:
        """
        Generate response expressing specific emotion
        """
        prompt = f"Express {emotion} with intensity {intensity:.1f}/10.0"
        
        return self.chat(
            prompt,
            personality,
            [],
            None
        )
    
    def summarize_conversation(
        self,
        conversation_history: List[Message]
    ) -> str:
        """
        Summarize conversation for memory/context
        """
        if not conversation_history:
            return "No conversation yet."
        
        # Create summary prompt
        conv_text = "\n".join([
            f"{msg.role}: {msg.content}"
            for msg in conversation_history
        ])
        
        messages = [
            {
                "role": "system",
                "content": "Summarize the following conversation in 2-3 sentences."
            },
            {
                "role": "user",
                "content": conv_text
            }
        ]
        
        if self.provider == "openai":
            return self._chat_openai(messages)
        elif self.provider == "anthropic":
            return self._chat_anthropic(messages)
    
    def extract_intent(self, message: str) -> Dict:
        """
        Extract user intent from message
        """
        prompt = f"""Analyze this user message and extract:
1. Primary intent (question, statement, request, greeting, farewell)
2. Topic
3. Sentiment (positive, neutral, negative)
4. Requires action (yes/no)

Message: "{message}"

Respond in JSON format."""
        
        messages = [
            {"role": "system", "content": "You are an intent extraction system."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            if self.provider == "openai":
                response = self._chat_openai(messages)
            else:
                response = self._chat_anthropic(messages)
            
            # Parse JSON response
            import json
            intent = json.loads(response)
            return intent
        except Exception as e:
            logger.error(f"Intent extraction failed: {e}")
            return {
                "intent": "unknown",
                "topic": "general",
                "sentiment": "neutral",
                "requires_action": False
            }
    
    def generate_personality_from_video(
        self,
        video_analysis: Dict
    ) -> CharacterPersonality:
        """
        Generate personality based on video analysis
        """
        # Extract information from video analysis
        appearance = video_analysis.get("appearance", {})
        behavior = video_analysis.get("behavior", {})
        context = video_analysis.get("context", {})
        
        # Generate personality using AI
        prompt = f"""Based on this video analysis, create a character personality:

Appearance: {appearance}
Behavior: {behavior}
Context: {context}

Generate:
1. Name (if not known, create appropriate one)
2. Estimated age
3. Background story (2-3 sentences)
4. 5 personality traits
5. Speaking style
6. 3 interests

Respond in JSON format."""
        
        messages = [
            {"role": "system", "content": "You are a character personality generator."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            if self.provider == "openai":
                response = self._chat_openai(messages)
            else:
                response = self._chat_anthropic(messages)
            
            import json
            personality_data = json.loads(response)
            
            return CharacterPersonality(
                name=personality_data.get("name", "Unknown"),
                age=personality_data.get("age"),
                background=personality_data.get("background", ""),
                traits=personality_data.get("traits", []),
                speaking_style=personality_data.get("speaking_style", "casual"),
                interests=personality_data.get("interests", [])
            )
        except Exception as e:
            logger.error(f"Personality generation failed: {e}")
            return CharacterPersonality(name="Unknown")
    
    def moderate_content(self, text: str) -> Dict:
        """
        Check if content is appropriate
        """
        # Use OpenAI moderation API if available
        if self.provider == "openai":
            try:
                response = self.client.moderations.create(input=text)
                result = response.results[0]
                
                return {
                    "flagged": result.flagged,
                    "categories": result.categories.model_dump(),
                    "safe": not result.flagged
                }
            except Exception as e:
                logger.error(f"Moderation failed: {e}")
        
        # Default: assume safe
        return {"flagged": False, "safe": True}

# Made with Bob
