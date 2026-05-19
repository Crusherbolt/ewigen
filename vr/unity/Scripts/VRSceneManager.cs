using UnityEngine;
using UnityEngine.XR;
using System.Collections;
using System.Collections.Generic;
using UnityEngine.Networking;

/// <summary>
/// Main VR Scene Manager
/// Handles loading 3D scenes, characters, and interactions
/// </summary>
public class VRSceneManager : MonoBehaviour
{
    [Header("API Configuration")]
    [SerializeField] private string apiBaseUrl = "http://localhost:8000/api/v1";
    [SerializeField] private string accessToken;

    [Header("Scene Settings")]
    [SerializeField] private GameObject sceneContainer;
    [SerializeField] private Material defaultMaterial;
    
    [Header("Character Settings")]
    [SerializeField] private GameObject characterPrefab;
    [SerializeField] private Transform characterContainer;

    [Header("VR Settings")]
    [SerializeField] private Transform vrCamera;
    [SerializeField] private Transform leftHand;
    [SerializeField] private Transform rightHand;

    private int currentProjectId;
    private Dictionary<int, GameObject> loadedCharacters = new Dictionary<int, GameObject>();
    private bool isSceneLoaded = false;

    void Start()
    {
        // Initialize VR
        InitializeVR();
        
        // Load access token from PlayerPrefs
        accessToken = PlayerPrefs.GetString("access_token", "");
        
        if (string.IsNullOrEmpty(accessToken))
        {
            Debug.LogError("No access token found. Please login first.");
            return;
        }

        // Load project from command line args or default
        currentProjectId = GetProjectIdFromArgs();
        
        if (currentProjectId > 0)
        {
            StartCoroutine(LoadProject(currentProjectId));
        }
    }

    void InitializeVR()
    {
        // Check if VR is available
        if (!XRSettings.enabled)
        {
            Debug.LogWarning("VR not enabled. Running in desktop mode.");
            return;
        }

        Debug.Log($"VR Device: {XRSettings.loadedDeviceName}");
        Debug.Log($"VR Supported: {XRSettings.isDeviceActive}");
    }

    int GetProjectIdFromArgs()
    {
        string[] args = System.Environment.GetCommandLineArgs();
        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "-projectId" && i + 1 < args.Length)
            {
                if (int.TryParse(args[i + 1], out int projectId))
                {
                    return projectId;
                }
            }
        }
        return 1; // Default project ID
    }

    IEnumerator LoadProject(int projectId)
    {
        Debug.Log($"Loading project {projectId}...");

        // Get project details
        UnityWebRequest request = UnityWebRequest.Get($"{apiBaseUrl}/projects/{projectId}");
        request.SetRequestHeader("Authorization", $"Bearer {accessToken}");

        yield return request.SendWebRequest();

        if (request.result != UnityWebRequest.Result.Success)
        {
            Debug.LogError($"Failed to load project: {request.error}");
            yield break;
        }

        string jsonResponse = request.downloadHandler.text;
        ProjectData projectData = JsonUtility.FromJson<ProjectData>(jsonResponse);

        Debug.Log($"Project loaded: {projectData.name}");

        // Load scene
        yield return StartCoroutine(LoadScene(projectId));

        // Load characters
        yield return StartCoroutine(LoadCharacters(projectId));

        isSceneLoaded = true;
        Debug.Log("Project loaded successfully!");
    }

    IEnumerator LoadScene(int projectId)
    {
        Debug.Log("Loading 3D scene...");

        // Get scene data
        UnityWebRequest request = UnityWebRequest.Get($"{apiBaseUrl}/projects/{projectId}/scenes");
        request.SetRequestHeader("Authorization", $"Bearer {accessToken}");

        yield return request.SendWebRequest();

        if (request.result != UnityWebRequest.Result.Success)
        {
            Debug.LogError($"Failed to load scene: {request.error}");
            yield break;
        }

        string jsonResponse = request.downloadHandler.text;
        SceneListData sceneList = JsonUtility.FromJson<SceneListData>(jsonResponse);

        if (sceneList.scenes.Length == 0)
        {
            Debug.LogWarning("No scenes found for this project");
            yield break;
        }

        // Load first scene
        SceneData scene = sceneList.scenes[0];
        
        // Download scene model (NeRF or Gaussian Splatting)
        yield return StartCoroutine(DownloadAndLoadSceneModel(scene));
    }

    IEnumerator DownloadAndLoadSceneModel(SceneData scene)
    {
        // TODO: Download scene model file (GLB, USD, or custom format)
        // For now, create a placeholder
        
        GameObject sceneObject = GameObject.CreatePrimitive(PrimitiveType.Cube);
        sceneObject.transform.SetParent(sceneContainer.transform);
        sceneObject.transform.localPosition = Vector3.zero;
        sceneObject.transform.localScale = new Vector3(10, 0.1f, 10); // Floor
        
        if (defaultMaterial != null)
        {
            sceneObject.GetComponent<Renderer>().material = defaultMaterial;
        }

        Debug.Log("Scene model loaded (placeholder)");
        yield return null;
    }

    IEnumerator LoadCharacters(int projectId)
    {
        Debug.Log("Loading characters...");

        UnityWebRequest request = UnityWebRequest.Get($"{apiBaseUrl}/projects/{projectId}/characters");
        request.SetRequestHeader("Authorization", $"Bearer {accessToken}");

        yield return request.SendWebRequest();

        if (request.result != UnityWebRequest.Result.Success)
        {
            Debug.LogError($"Failed to load characters: {request.error}");
            yield break;
        }

        string jsonResponse = request.downloadHandler.text;
        CharacterListData characterList = JsonUtility.FromJson<CharacterListData>(jsonResponse);

        Debug.Log($"Found {characterList.characters.Length} characters");

        foreach (CharacterData character in characterList.characters)
        {
            yield return StartCoroutine(LoadCharacter(character));
        }
    }

    IEnumerator LoadCharacter(CharacterData character)
    {
        Debug.Log($"Loading character: {character.name}");

        // Create character object
        GameObject characterObj;
        
        if (characterPrefab != null)
        {
            characterObj = Instantiate(characterPrefab, characterContainer);
        }
        else
        {
            // Create placeholder
            characterObj = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            characterObj.transform.SetParent(characterContainer);
        }

        characterObj.name = $"Character_{character.id}";
        characterObj.transform.localPosition = new Vector3(
            Random.Range(-3f, 3f),
            0f,
            Random.Range(-3f, 3f)
        );

        // Add character controller
        VRCharacterController controller = characterObj.AddComponent<VRCharacterController>();
        controller.Initialize(character, apiBaseUrl, accessToken);

        loadedCharacters[character.id] = characterObj;

        yield return null;
    }

    public void InteractWithCharacter(int characterId)
    {
        if (loadedCharacters.TryGetValue(characterId, out GameObject characterObj))
        {
            VRCharacterController controller = characterObj.GetComponent<VRCharacterController>();
            if (controller != null)
            {
                controller.StartInteraction();
            }
        }
    }

    void Update()
    {
        if (!isSceneLoaded) return;

        // Handle VR input
        HandleVRInput();
    }

    void HandleVRInput()
    {
        // Get controller input
        if (XRSettings.enabled)
        {
            // Left controller
            InputDevice leftDevice = InputDevices.GetDeviceAtXRNode(XRNode.LeftHand);
            if (leftDevice.TryGetFeatureValue(CommonUsages.triggerButton, out bool leftTrigger) && leftTrigger)
            {
                OnLeftTriggerPressed();
            }

            // Right controller
            InputDevice rightDevice = InputDevices.GetDeviceAtXRNode(XRNode.RightHand);
            if (rightDevice.TryGetFeatureValue(CommonUsages.triggerButton, out bool rightTrigger) && rightTrigger)
            {
                OnRightTriggerPressed();
            }
        }
        else
        {
            // Desktop fallback
            if (Input.GetMouseButtonDown(0))
            {
                OnLeftTriggerPressed();
            }
        }
    }

    void OnLeftTriggerPressed()
    {
        // Raycast from left hand
        RaycastHit hit;
        if (Physics.Raycast(leftHand.position, leftHand.forward, out hit, 10f))
        {
            VRCharacterController character = hit.collider.GetComponent<VRCharacterController>();
            if (character != null)
            {
                character.StartInteraction();
            }
        }
    }

    void OnRightTriggerPressed()
    {
        // Raycast from right hand
        RaycastHit hit;
        if (Physics.Raycast(rightHand.position, rightHand.forward, out hit, 10f))
        {
            VRCharacterController character = hit.collider.GetComponent<VRCharacterController>();
            if (character != null)
            {
                character.StartInteraction();
            }
        }
    }
}

// Data classes for JSON deserialization
[System.Serializable]
public class ProjectData
{
    public int id;
    public string name;
    public string description;
    public string status;
    public float progress;
}

[System.Serializable]
public class SceneData
{
    public int id;
    public string name;
    public string scene_type;
    public float quality_score;
}

[System.Serializable]
public class SceneListData
{
    public SceneData[] scenes;
}

[System.Serializable]
public class CharacterData
{
    public int id;
    public string name;
    public int track_id;
    public bool has_voice_model;
    public bool has_avatar;
}

[System.Serializable]
public class CharacterListData
{
    public CharacterData[] characters;
}

// Made with Bob
