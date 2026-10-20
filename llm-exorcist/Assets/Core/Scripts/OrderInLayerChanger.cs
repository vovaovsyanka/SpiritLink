using UnityEngine;

public class OrderInLayerChanger : MonoBehaviour
{
    private int _underPlayerOrderInLayer;
    private int _overPlayerOrderInLayer;
    private SpriteRenderer _spriteRenderer;

    private void Start()
    {
        _spriteRenderer = GetComponent<SpriteRenderer>();

        _overPlayerOrderInLayer = Player.Instance.SpriteRenderer.sortingOrder + 1;
        _underPlayerOrderInLayer = Player.Instance.SpriteRenderer.sortingOrder - 1;
    }

    void Update()
    {
        if(Player.Instance.transform.position.y >
            transform.position.y)
        {
            _spriteRenderer.sortingOrder = _overPlayerOrderInLayer;
        }
        else
        {
            _spriteRenderer.sortingOrder = _underPlayerOrderInLayer;
        }
    }
}
