using UnityEngine;

public class Leviathan : MonoBehaviour
{
    [SerializeField] private int _timeToDestroy = 10;
    [SerializeField] private GameObject _visual;

    private void Start()
    {
        _visual.SetActive(false);
    }

    private void OnTriggerEnter2D(Collider2D collision)
    {
        _visual.SetActive(true);
        Destroy(gameObject, _timeToDestroy);
    }
}
