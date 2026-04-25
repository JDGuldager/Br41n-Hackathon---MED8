using UnityEngine;
using UnityEngine.EventSystems;

public class CDHover : MonoBehaviour, IPointerEnterHandler, IPointerExitHandler
{
    public float hoverAmount = 0.35f;
    public float hoverSpeed = 8f;

    private Vector3 startLocalPos;
    private Vector3 targetLocalPos;

    void Start()
    {
        startLocalPos = transform.localPosition;
        targetLocalPos = startLocalPos;
    }

    void Update()
    {
        transform.localPosition = Vector3.Lerp(
            transform.localPosition,
            targetLocalPos,
            Time.deltaTime * hoverSpeed
        );
    }

    public void OnPointerEnter(PointerEventData eventData)
    {
        targetLocalPos = startLocalPos + Vector3.up * hoverAmount;
    }

    public void OnPointerExit(PointerEventData eventData)
    {
        targetLocalPos = startLocalPos;
    }
}