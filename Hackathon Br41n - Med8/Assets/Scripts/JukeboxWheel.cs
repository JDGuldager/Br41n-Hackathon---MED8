using UnityEngine;

public class JukeboxWheel : MonoBehaviour
{
    [Header("CD Setup")]
    public float radius = 3f;
    public float cdHeight = 0f;
    public float selectedHeightOffset = 0.5f;

    [Header("Transparency")]
    public float selectedAlpha = 1f;
    public float unselectedAlpha = 0.4f;

    private Renderer[] renderers;
    private float[] alphaVelocities;

    [Header("Selected CD Effects")]
    public float selectedScale = 1.15f;
    public float selectedForwardPush = 0.25f;
    public float effectSmoothTime = 0.12f;

    [Header("CD Facing")]
    public float cdYRotationOffset = 90f;

    [Header("Selection")]
    public float selectionAngleOffset = -30f;

    [Header("Rotation")]
    public float rotationSmoothTime = 0.18f;

    private Transform[] cds;
    private Vector3[] basePositions;
    private Vector3[] baseScales;
    private Vector3[] positionVelocities;
    private Vector3[] scaleVelocities;

    private float targetYRotation;
    private float rotationVelocity;
    private int selectedIndex = 0;

    void Awake()
    {
        CollectChildren();
        ArrangeCDs();
        targetYRotation = transform.eulerAngles.y;
    }

    void Update()
    {
        if (cds == null || cds.Length == 0) return;

        float currentY = transform.eulerAngles.y;

        float smoothedY = Mathf.SmoothDampAngle(
            currentY,
            targetYRotation,
            ref rotationVelocity,
            rotationSmoothTime
        );

        transform.rotation = Quaternion.Euler(0f, smoothedY, 0f);

        AnimateTransparency();
        UpdateSelectedCD();
        AnimateCDs();
    }

    public void RotateLeft()
    {
        if (cds == null || cds.Length == 0) return;
        targetYRotation += 360f / cds.Length;
    }

    public void RotateRight()
    {
        if (cds == null || cds.Length == 0) return;
        targetYRotation -= 360f / cds.Length;
    }

    private void CollectChildren()
    {
        int count = transform.childCount;

        cds = new Transform[count];
        basePositions = new Vector3[count];
        baseScales = new Vector3[count];
        positionVelocities = new Vector3[count];
        scaleVelocities = new Vector3[count];
        renderers = new Renderer[count];
        alphaVelocities = new float[count];

        for (int i = 0; i < count; i++)
        {
            cds[i] = transform.GetChild(i);

            baseScales[i] = cds[i].localScale;

            renderers[i] = cds[i].GetComponentInChildren<Renderer>();
        }
    }

    private void ArrangeCDs()
    {
        if (cds == null || cds.Length == 0) return;

        float angleStep = 360f / cds.Length;

        for (int i = 0; i < cds.Length; i++)
        {
            float angleDeg = i * angleStep;
            float angleRad = angleDeg * Mathf.Deg2Rad;

            Vector3 localPos = new Vector3(
                Mathf.Sin(angleRad) * radius,
                cdHeight,
                Mathf.Cos(angleRad) * radius
            );

            cds[i].localPosition = localPos;
            basePositions[i] = localPos;

            cds[i].localRotation = Quaternion.Euler(
                0f,
                angleDeg + cdYRotationOffset,
                0f
            );
        }
    }

    private void UpdateSelectedCD()
    {
        float angleStep = 360f / cds.Length;
        float wheelY = transform.eulerAngles.y;

        float targetAngle = -wheelY + selectionAngleOffset;
        int closestIndex = Mathf.RoundToInt(targetAngle / angleStep);

        selectedIndex = Mod(closestIndex, cds.Length);
    }

    private void AnimateCDs()
    {
        for (int i = 0; i < cds.Length; i++)
        {
            Vector3 targetPos = basePositions[i];
            Vector3 targetScale = baseScales[i];

            if (i == selectedIndex)
            {
                targetPos.y = cdHeight + selectedHeightOffset;

                Vector3 pushDirection = transform.InverseTransformDirection(
                    Camera.main.transform.forward
                );

                targetPos += pushDirection.normalized * selectedForwardPush;

                targetScale = baseScales[i] * selectedScale;
            }

            cds[i].localPosition = Vector3.SmoothDamp(
                cds[i].localPosition,
                targetPos,
                ref positionVelocities[i],
                effectSmoothTime
            );

            cds[i].localScale = Vector3.SmoothDamp(
                cds[i].localScale,
                targetScale,
                ref scaleVelocities[i],
                effectSmoothTime
            );
        }
    }

    private int Mod(int value, int length)
    {
        return ((value % length) + length) % length;
    }

    private void AnimateTransparency()
    {
        for (int i = 0; i < cds.Length; i++)
        {
            if (renderers[i] == null) continue;

            float targetAlpha = (i == selectedIndex) ? selectedAlpha : unselectedAlpha;

            Material mat = renderers[i].material;
            Color color = mat.color;

            // Slower, more noticeable easing
            float smoothTime = effectSmoothTime * 1.5f;

            float newAlpha = Mathf.SmoothDamp(
                color.a,
                targetAlpha,
                ref alphaVelocities[i],
                smoothTime
            );

            color.a = newAlpha;
            mat.color = color;
        }
    }

    void OnValidate()
    {
        if (!Application.isPlaying)
        {
            CollectChildren();
            ArrangeCDs();
        }
    }
}