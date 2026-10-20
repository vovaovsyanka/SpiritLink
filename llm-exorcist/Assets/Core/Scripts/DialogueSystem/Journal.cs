using System;
using UnityEngine;
using UnityEngine.UI;

public class Journal : MonoBehaviour
{
    [SerializeField] private Button _journalButton;
    [SerializeField] private GameObject _journalMask;
    [Space(20)]
    [SerializeField] private Transform _journalContent;
    [Space(20)]
    [SerializeField] private GameObject _simplePhrase;
    [SerializeField] private GameObject _space;
    private Animator _journalAnimator;

    public static bool IsJournalOpen { get; private set; }

    private void OnEnable()
    {
        DialogueViewer.OnCreditBookAction += SetJournalButton_OnCreditBookAction;
        DialogueViewer.OnPhraseChanged += SaveSimplePhrase;
        DialogueViewer.OnCreditBookAction += CreateSpace;

        _journalButton.onClick.AddListener(OpenCloseJournal);

        IsJournalOpen = false;
        _journalMask.SetActive(false);
        _journalAnimator = gameObject.GetComponent<Animator>();
    }

    private void OnDisable()
    {
        DialogueViewer.OnCreditBookAction -= SetJournalButton_OnCreditBookAction;
        DialogueViewer.OnPhraseChanged -= SaveSimplePhrase;
        DialogueViewer.OnCreditBookAction -= CreateSpace;

        _journalButton.onClick.RemoveListener(OpenCloseJournal);
    }

    private void SaveSimplePhrase(DialogueBaseClass phraseData)
    {
        JournalSimplePhrase currentSimplePhrase = Instantiate(_simplePhrase, _journalContent).GetComponent<JournalSimplePhrase>();
        currentSimplePhrase.Name.text = phraseData.simplePhrase.InputName;
        currentSimplePhrase.Text.text = phraseData.simplePhrase.InputText;
    }

    private void CreateSpace(object sender, EventArgs e)
    {
        Instantiate(_space, _journalContent);
    }

    private void OpenCloseJournal()
    {
        if (IsJournalOpen)
        {
            _journalAnimator.SetBool("IsOn", false);
        }
        else
        {
            _journalAnimator.SetBool("IsOn", true);
        }
    }

    private void EnableDisableMask()
    {
        _journalMask.SetActive(!_journalMask.activeSelf);
        IsJournalOpen = _journalMask.activeSelf;
    }

    private void SetJournalButton_OnCreditBookAction(object sender, EventArgs e)
    {
        _journalButton.interactable = !_journalButton.IsInteractable();
    }
}