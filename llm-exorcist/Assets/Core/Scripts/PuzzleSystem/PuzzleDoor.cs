using System;
using System.Collections;
using UnityEngine;

public class PuzzleDoor : MonoBehaviour
{
    public event Action OnPuzzleStart;
    public event Action OnPuzzleEnd;

    [SerializeField] private FadeScreen _fadeScreen;
    [SerializeField] private Transform _afterSolvedPuzzleTransform;
    [Space(20)]
    [SerializeField] private GameObject _locationBeforePuzzle;
    [SerializeField] private GameObject _locationAfterPuzzle;

    private bool _isOpened;

    private void Start()
    {
        // OpenInstantly мог быть вызван раньше Start (прогресс с сервера пришёл быстро)
        SetLocation(opened: _isOpened);
    }

    /// <summary>Паззл решён в прошлый заход: без затемнения сразу ставим игрока за дверь.</summary>
    public void OpenInstantly()
    {
        if (_isOpened) return;
        _isOpened = true;

        SetLocation(opened: true);
        var player = Player.Instance;
        if (player != null && _afterSolvedPuzzleTransform != null)
        {
            player.transform.position = _afterSolvedPuzzleTransform.position;
        }
        OnPuzzleEnd?.Invoke();
    }

    [ContextMenu("Open Door")]
    public void OpenDoor()
    {
        if (_isOpened) return;
        _isOpened = true;

        StartCoroutine(OpenDoorRoutine());
    }

    private IEnumerator OpenDoorRoutine()
    {
        var player = Player.Instance;
        if (player != null)
        {
            player.CanAct = false;
        }

        if (_fadeScreen != null)
        {
            yield return StartCoroutine(_fadeScreen.Fade());
        }

        SetLocation(opened: true);
        if (player != null && _afterSolvedPuzzleTransform != null)
        {
            player.transform.position = _afterSolvedPuzzleTransform.position;
        }

        // старый триггер мог отключиться вместе с локацией, не вызвав OnTriggerExit2D
        OnPuzzleEnd?.Invoke();

        if (_fadeScreen != null)
        {
            StartCoroutine(_fadeScreen.Appear());
        }
        if (player != null)
        {
            player.CanAct = true;
        }
    }

    private void SetLocation(bool opened)
    {
        if (_locationBeforePuzzle != null) _locationBeforePuzzle.SetActive(!opened);
        if (_locationAfterPuzzle != null) _locationAfterPuzzle.SetActive(opened);
    }

    private void OnTriggerEnter2D(Collider2D collision)
    {
        if (_isOpened || !IsPlayer(collision)) return;

        OnPuzzleStart?.Invoke();
    }

    private void OnTriggerExit2D(Collider2D collision)
    {
        if (!IsPlayer(collision)) return;

        OnPuzzleEnd?.Invoke();
    }

    private static bool IsPlayer(Collider2D collision)
    {
        return collision.GetComponentInParent<Player>() != null;
    }
}
