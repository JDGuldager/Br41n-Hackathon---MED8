using System.Collections.Generic;
using UnityEngine;

public class CDSelectionManager : MonoBehaviour
{
    [Header("Settings")]
    public int maxSelectedCDs = 4;

    [Header("Volume")]
    public float selectedVolume = 1f;
    public float hoveredVolume = 0.6f;
    public float mutedVolume = 0f;
    public float volumeFadeSpeed = 6f;

    [Header("Selected CD Names")]
    public List<string> selectedCDs = new List<string>();

    private List<Transform> selectedCDTransforms = new List<Transform>();
    private Dictionary<Transform, AudioSource> audioSources =
        new Dictionary<Transform, AudioSource>();

    private Transform hoveredCD;

    void Update()
    {
        UpdateVolumes();
    }

    public void RegisterCDs(Transform[] cds)
    {
        foreach (Transform cd in cds)
        {
            if (cd == null) continue;

            CDAudio cdAudio = cd.GetComponent<CDAudio>();

            if (cdAudio == null || cdAudio.clip == null)
            {
                Debug.LogWarning("Missing CDAudio or AudioClip on CD: " + cd.name);
                continue;
            }

            AudioSource source = GetAudioSource(cd);

            source.clip = cdAudio.clip;
            source.loop = true;
            source.playOnAwake = false;
            source.spatialBlend = 0f;
            source.volume = 0f;

            if (!source.isPlaying)
            {
                source.Play();
            }
        }
    }

    public void SetHoveredCD(Transform cd)
    {
        hoveredCD = cd;
    }

    public void ToggleCD(Transform cd)
    {
        if (cd == null) return;

        string cdName = cd.name;

        if (selectedCDTransforms.Contains(cd))
        {
            selectedCDTransforms.Remove(cd);
            selectedCDs.Remove(cdName);

            Debug.Log("Unselected CD: " + cdName);
        }
        else
        {
            if (selectedCDTransforms.Count >= maxSelectedCDs)
            {
                Debug.Log("Maximum selected CDs reached.");
                return;
            }

            selectedCDTransforms.Add(cd);

            if (!selectedCDs.Contains(cdName))
            {
                selectedCDs.Add(cdName);
            }

            Debug.Log("Selected CD: " + cdName);
        }
    }

    public bool IsSelected(Transform cd)
    {
        return cd != null && selectedCDTransforms.Contains(cd);
    }

    public List<string> GetSelectedCDNames()
    {
        return selectedCDs;
    }

    public List<Transform> GetSelectedCDTransforms()
    {
        return selectedCDTransforms;
    }

    private void UpdateVolumes()
    {
        foreach (var pair in audioSources)
        {
            Transform cd = pair.Key;
            AudioSource source = pair.Value;

            if (source == null) continue;

            bool isSelected = selectedCDTransforms.Contains(cd);

            bool canHearHover =
                hoveredCD == cd &&
                !isSelected &&
                selectedCDTransforms.Count < maxSelectedCDs;

            float targetVolume = mutedVolume;

            if (isSelected)
            {
                targetVolume = selectedVolume;
            }
            else if (canHearHover)
            {
                targetVolume = hoveredVolume;
            }

            source.volume = Mathf.Lerp(
                source.volume,
                targetVolume,
                Time.deltaTime * volumeFadeSpeed
            );
        }
    }

    private AudioSource GetAudioSource(Transform cd)
    {
        if (audioSources.ContainsKey(cd))
            return audioSources[cd];

        AudioSource source = cd.gameObject.AddComponent<AudioSource>();
        audioSources.Add(cd, source);

        return source;
    }
}