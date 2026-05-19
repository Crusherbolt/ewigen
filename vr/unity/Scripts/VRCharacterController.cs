using UnityEngine;
using UnityEngine.Networking;
using System.Collections;
using System.Text;

/// <summary>
/// VR Character Controller
/// Handles character interactions, animations, and AI conversations
/// </summary>
public class VRCharacterController : MonoBehaviour
{
    [Header("Character Data")]
    private CharacterData characterData;
    private string apiBaseUrl;
    private string accessToken;

    [Header("Interaction")]
    [SerializeField] private float interactionDistance = 3f;
    [SerializeField] private GameObject interactionUI;
    [SerializeField] private AudioSource voiceAudioSource;

    [Header("Animation")]
    [SerializeField] private Animator animator;
    [SerializeField] private bool isAnimating = false;

    [Header("AI Conversation")]
    private bool isInConversation = false;
    private string conversationHistory = "";

    private Transform playerTransform;

    void Start()
    {
        // Find player camera
        playerTransform = Camera.main?.transform;
        
        // Setup audio source
        if (voiceAudioSource == null)
        {
            voiceAudioSource = gameObject.AddComponent<AudioSource>();
            voiceAudioSource.spatialBlend = 1.0f; // 3D sound
            voiceAudioSource.minDistance = 1f;
            voiceAudioSource.maxDistance = 10f;
        }

        // Setup animator if available
        if (animator == null)
        {
            animator = GetComponent<Animator>();
        }
    }

    public void Initialize(CharacterData data, string apiUrl, string token)
    {
        characterData = data;
        apiBaseUrl = apiUrl;
        accessToken = token;

        Debug.Log($"Character initialized: {characterData.name}");
    }

    void Update()
    {
        if (playerTransform == null) return;

        // Check distance to player
        float distance = Vector3.Distance(transform.position, playerTransform.position);
        
        // Show interaction UI if close enough
        if (interactionUI != null)
        {
            interactionUI.SetActive(distance <= interactionDistance && !isInConversation);
        }

        // Face player during conversation
        if (isInConversation)
        {
            FacePlayer();
        }
    }

    void FacePlayer()
    {
        Vector3 direction = playerTransform.position - transform.position;
        direction.y = 0; // Keep upright
        
        if (direction != Vector3.zero)
        {
            Quaternion targetRotation = Quaternion.LookRotation(direction);
            transform.rotation = Quaternion.Slerp(
                transform.rotation,
                targetRotation,
                Time.deltaTime * 5f
            );
        }
    }

    public void StartInteraction()
    {
        if (isInConversation) return;

        Debug.Log($"Starting interaction with {characterData.name}");
        isInConversation = true;

        // Play greeting animation
        PlayAnimation("wave");

        // Start conversation
        StartCoroutine(StartConversation());
    }

    public void EndInteraction()
    {
        Debug.Log($"Ending interaction with {characterData.name}");
        isInConversation = false;
        conversationHistory = "";

        // Play goodbye animation
        PlayAnimation("wave");
    }

    IEnumerator StartConversation()
    {
        // Generate greeting
        string greeting = $"Hello! I'm {characterData.name}. How can I help you?";
        
        yield return StartCoroutine(SpeakText(greeting));

        // Wait for user input (voice or text)
        // In a real implementation, this would use speech recognition
        yield return new WaitForSeconds(2f);

        // For demo, simulate a conversation
        yield return StartCoroutine(SimulateConversation());
    }

    IEnumerator SimulateConversation()
    {
        string[] demoMessages = new string[]
        {
            "It's great to see you!",
            "I remember this moment well.",
            "Would you like to dance with me?",
            "This was such a special day."
        };

        foreach (string message in demoMessages)
        {
            yield return new WaitForSeconds(3f);
            yield return StartCoroutine(SpeakText(message));
        }

        EndInteraction();
    }

    public void SendMessage(string userMessage)
    {
        if (!isInConversation) return;

        StartCoroutine(ProcessUserMessage(userMessage));
    }

    IEnumerator ProcessUserMessage(string userMessage)
    {
        Debug.Log($"User: {userMessage}");

        // Add to conversation history
        conversationHistory += $"User: {userMessage}\n";

        // Send to AI backend
        string aiResponse = "";
        yield return StartCoroutine(GetAIResponse(userMessage, (response) => {
            aiResponse = response;
        }));

        if (!string.IsNullOrEmpty(aiResponse))
        {
            conversationHistory += $"{characterData.name}: {aiResponse}\n";
            
            // Speak the response
            yield return StartCoroutine(SpeakText(aiResponse));
        }
    }

    IEnumerator GetAIResponse(string userMessage, System.Action<string> callback)
    {
        // Prepare request
        string url = $"{apiBaseUrl}/characters/{characterData.id}/chat";
        
        var requestData = new
        {
            message = userMessage,
            conversation_history = conversationHistory
        };

        string jsonData = JsonUtility.ToJson(requestData);
        byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonData);

        UnityWebRequest request = new UnityWebRequest(url, "POST");
        request.uploadHandler = new UploadHandlerRaw(bodyRaw);
        request.downloadHandler = new DownloadHandlerBuffer();
        request.SetRequestHeader("Content-Type", "application/json");
        request.SetRequestHeader("Authorization", $"Bearer {accessToken}");

        yield return request.SendWebRequest();

        if (request.result == UnityWebRequest.Result.Success)
        {
            string jsonResponse = request.downloadHandler.text;
            var response = JsonUtility.FromJson<AIResponseData>(jsonResponse);
            callback(response.response);
        }
        else
        {
            Debug.LogError($"AI request failed: {request.error}");
            callback("I'm sorry, I didn't catch that. Could you repeat?");
        }
    }

    IEnumerator SpeakText(string text)
    {
        Debug.Log($"{characterData.name}: {text}");

        // Play talking animation
        PlayAnimation("talk");

        if (characterData.has_voice_model)
        {
            // Generate speech using voice model
            yield return StartCoroutine(GenerateSpeech(text));
        }
        else
        {
            // Fallback: just wait for text duration
            float duration = text.Length * 0.05f; // Rough estimate
            yield return new WaitForSeconds(duration);
        }

        // Stop talking animation
        PlayAnimation("idle");
    }

    IEnumerator GenerateSpeech(string text)
    {
        string url = $"{apiBaseUrl}/characters/{characterData.id}/speak";
        
        var requestData = new
        {
            text = text
        };

        string jsonData = JsonUtility.ToJson(requestData);
        byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonData);

        UnityWebRequest request = new UnityWebRequest(url, "POST");
        request.uploadHandler = new UploadHandlerRaw(bodyRaw);
        request.downloadHandler = new DownloadHandlerAudioClip(url, AudioType.WAV);
        request.SetRequestHeader("Content-Type", "application/json");
        request.SetRequestHeader("Authorization", $"Bearer {accessToken}");

        yield return request.SendWebRequest();

        if (request.result == UnityWebRequest.Result.Success)
        {
            AudioClip audioClip = DownloadHandlerAudioClip.GetContent(request);
            
            if (audioClip != null && voiceAudioSource != null)
            {
                voiceAudioSource.clip = audioClip;
                voiceAudioSource.Play();
                
                // Wait for audio to finish
                yield return new WaitForSeconds(audioClip.length);
            }
        }
        else
        {
            Debug.LogError($"Speech generation failed: {request.error}");
            // Fallback to text duration
            yield return new WaitForSeconds(text.Length * 0.05f);
        }
    }

    void PlayAnimation(string animationName)
    {
        if (animator == null) return;

        switch (animationName)
        {
            case "idle":
                animator.SetBool("isWalking", false);
                animator.SetBool("isTalking", false);
                animator.SetTrigger("idle");
                break;
            
            case "wave":
                animator.SetTrigger("wave");
                break;
            
            case "talk":
                animator.SetBool("isTalking", true);
                break;
            
            case "dance":
                animator.SetTrigger("dance");
                break;
            
            case "walk":
                animator.SetBool("isWalking", true);
                break;
        }
    }

    public void PlayCustomAnimation(string animationName)
    {
        PlayAnimation(animationName);
    }

    public void MoveToPosition(Vector3 targetPosition)
    {
        StartCoroutine(MoveToPositionCoroutine(targetPosition));
    }

    IEnumerator MoveToPositionCoroutine(Vector3 targetPosition)
    {
        PlayAnimation("walk");

        float speed = 2f;
        while (Vector3.Distance(transform.position, targetPosition) > 0.1f)
        {
            transform.position = Vector3.MoveTowards(
                transform.position,
                targetPosition,
                speed * Time.deltaTime
            );

            // Face movement direction
            Vector3 direction = targetPosition - transform.position;
            if (direction != Vector3.zero)
            {
                transform.rotation = Quaternion.LookRotation(direction);
            }

            yield return null;
        }

        PlayAnimation("idle");
    }

    void OnDrawGizmosSelected()
    {
        // Draw interaction radius
        Gizmos.color = Color.yellow;
        Gizmos.DrawWireSphere(transform.position, interactionDistance);
    }
}

[System.Serializable]
public class AIResponseData
{
    public string response;
    public string emotion;
}

[System.Serializable]
public class SpeechRequestData
{
    public string text;
}

// Made with Bob
