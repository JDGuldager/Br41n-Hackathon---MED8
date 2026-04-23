using System.Collections;
using UnityEngine;
using UnityEngine.UI;

public class BrainCube : MonoBehaviour
{
    [Header("References")]
    public UnicornBandpowerUdpReceiver receiver;

    [Header("Signal Selection")]
    public bool useAlpha = true;
    public bool useBeta = false;
    public bool useGamma = false;

    [Header("Calibration")]
    public float calibrationDuration = 5f;
    public bool isCalibrating = false;
    public bool isCalibrated = false;
    public float baseline = 1f;

    [Header("Smoothing")]
    [Tooltip("Higher = faster response, lower = smoother")]
    public float smoothSpeed = 5f;
    private float smoothedSignal = 0f;

    [Header("Scaling")]
    public float multiplier = 2f;
    public float minY = 0.5f;
    public float maxY = 5f;

    [Header("Debug")]
    public float rawSignal = 0f;
    public float normalizedSignal = 0f;

    [Header("Optional UI")]
    public Text statusText;

    void Update()
    {
        rawSignal = GetSelectedSignal();

        float targetSignal = rawSignal;

        if (isCalibrated && baseline > 0.0001f)
            normalizedSignal = rawSignal / baseline;
        else
            normalizedSignal = rawSignal;

        // Low-pass smoothing
        smoothedSignal = Mathf.Lerp(smoothedSignal, normalizedSignal, Time.deltaTime * smoothSpeed);

        float y = Mathf.Clamp(smoothedSignal * multiplier, minY, maxY);
        transform.localScale = new Vector3(1f, y, 1f);

        UpdateStatusText();
    }

    float GetSelectedSignal()
    {
        if (receiver == null)
            return 0f;

        if (useAlpha) return receiver.alphaAverage;
        if (useBeta) return receiver.betaAverage;
        if (useGamma) return receiver.gammaAverage;

        return receiver.alphaAverage;
    }

    public void StartCalibration()
    {
        if (!isCalibrating)
            StartCoroutine(CalibrateRoutine());
    }

    IEnumerator CalibrateRoutine()
    {
        isCalibrating = true;
        isCalibrated = false;

        float sum = 0f;
        int count = 0;
        float timer = 0f;

        Debug.Log("Calibration started.");

        while (timer < calibrationDuration)
        {
            float value = GetSelectedSignal();

            if (!float.IsNaN(value) && value > 0f)
            {
                sum += value;
                count++;
            }

            timer += Time.deltaTime;
            yield return null;
        }

        if (count > 0)
        {
            baseline = sum / count;
            isCalibrated = true;
            Debug.Log($"Calibration finished. Baseline = {baseline:F4}");
        }
        else
        {
            Debug.LogWarning("Calibration failed: no valid samples received.");
        }

        isCalibrating = false;
    }

    public void ResetCalibration()
    {
        baseline = 1f;
        isCalibrated = false;
        isCalibrating = false;
        Debug.Log("Calibration reset.");
    }

    void UpdateStatusText()
    {
        if (statusText == null)
            return;

        string signalName = useAlpha ? "Alpha" : useBeta ? "Beta" : "Gamma";

        if (isCalibrating)
        {
            statusText.text = $"Calibrating {signalName}...";
        }
        else if (isCalibrated)
        {
            statusText.text =
                $"{signalName}\n" +
                $"Raw: {rawSignal:F3}\n" +
                $"Baseline: {baseline:F3}\n" +
                $"Normalized: {normalizedSignal:F3}";
        }
        else
        {
            statusText.text =
                $"{signalName}\n" +
                $"Raw: {rawSignal:F3}\n" +
                $"Not calibrated";
        }
    }
}