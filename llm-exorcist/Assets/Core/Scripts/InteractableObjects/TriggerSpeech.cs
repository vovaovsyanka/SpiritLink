using UnityEngine;

[RequireComponent(typeof(Collider2D), typeof(DialogueViewer))]
public class TriggerSpeech : InteractableObject
{
    [Space(30)]
    [SerializeField] private bool _isStatable = true;
    [SerializeField] GameState _nessecaryState;
    private DialogueViewer _dialogueViewer;
    private bool _isSpeechEnabled;

    private void Start()
    {
        _dialogueViewer = GetComponent<DialogueViewer>();
    }

    public override bool TrySelect()
    {
        if ((_isInteractable && GameStateManager.State == _nessecaryState) || (_isInteractable && !_isStatable))
        {
            if (!_isSpeechEnabled)
            {
                StartCoroutine(_dialogueViewer.Starter());
                _isSpeechEnabled = true;
            }
        }
        return _isInteractable;
    }

    public override void Interact()
    {

        return;
    }

    public override void Deselect()
    {
        return;
    }
}
