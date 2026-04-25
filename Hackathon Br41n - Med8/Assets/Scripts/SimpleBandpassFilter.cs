using UnityEngine;

public class SimpleBandpassFilter : MonoBehaviour
{
    private AudioLowPassFilter lowPass;
    private AudioHighPassFilter highPass;
    public BrainInputController controller;
    public float cutoff;

    void Start()
    {
        // Dodaj komponenty jeśli ich nie ma
        lowPass = gameObject.GetComponent<AudioLowPassFilter>();
        if (lowPass == null)
            lowPass = gameObject.AddComponent<AudioLowPassFilter>();

        highPass = gameObject.GetComponent<AudioHighPassFilter>();
        if (highPass == null)
            highPass = gameObject.AddComponent<AudioHighPassFilter>();

        // Ustaw domyślne wartości
        SetFilterActive(false);
    }
    private void Update()
    {
        //if (BrainInputController. < cutoff)
        { SetFilterActive(true); }
    }
    public void SetFilterActive(bool active)
    {
        if (active)
        {
            lowPass.enabled = true;
            lowPass.cutoffFrequency = 5000f;  // Częstotliwość górna

            highPass.enabled = true;
            highPass.cutoffFrequency = 100f;  // Częstotliwość dolna
        }
        else
        {
            lowPass.enabled = false;
            highPass.enabled = false;
        }
    }
}