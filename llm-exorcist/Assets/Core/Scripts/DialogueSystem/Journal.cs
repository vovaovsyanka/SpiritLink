using System;
using System.Collections.Generic;
using System.Linq;
using Core.Scripts.Network;
using UnityEngine;
using UnityEngine.UI;

public class Journal : MonoBehaviour
{
    // Ограничения сервера (bek-project/app/schemas.py: JournalEntry, JournalRequest)
    private const int MaxNameLength = 200;
    private const int MaxTextLength = 2000;
    private const int MaxEntriesPerDialogue = 200;

    [SerializeField] private Button _journalButton;
    [SerializeField] private GameObject _journalMask;
    [Space(20)]
    [SerializeField] private Transform _journalContent;
    [Space(20)]
    [SerializeField] private GameObject _simplePhrase;
    [SerializeField] private GameObject _space;
    private Animator _journalAnimator;

    // Текущий разговор: его записи в журнале и реплики — чтобы убрать повтор или сохранить на сервер
    private readonly List<GameObject> _currentObjects = new();
    private readonly List<JournalEntry> _currentEntries = new();
    // Уже записанные разговоры (сохранённые и прочитанные в этот заход) — повторы не пишем
    private readonly HashSet<string> _knownDialogues = new();
    // Сохранённые разговоры вставляются в начало журнала, перед прочитанными в этот заход
    private int _restoredSiblingIndex;

    public static bool IsJournalOpen { get; private set; }
    /// <summary>Разговор впервые попал в журнал — его нужно сохранить на сервере.</summary>
    public static event Action<JournalEntry[]> OnDialogueRecorded;

    private void OnEnable()
    {
        DialogueViewer.OnCreditBookAction += SetJournalButton_OnCreditBookAction;
        DialogueViewer.OnPhraseChanged += SaveSimplePhrase;
        DialogueViewer.OnCreditBookAction += CreateSpace;
        DialogueViewer.OnConversationFinished += FinishDialogue;

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
        DialogueViewer.OnConversationFinished -= FinishDialogue;

        _journalButton.onClick.RemoveListener(OpenCloseJournal);
    }

    /// <summary>Разговоры, прочитанные в прошлые заходы (с сервера).</summary>
    public void RestoreSaved(JournalDialogue[] saved)
    {
        if (saved == null) return;

        foreach (var dialogue in saved)
        {
            if (dialogue?.entries == null || dialogue.entries.Length == 0) continue;
            // уже прочитан в этот заход, пока ждали ответ сервера
            if (!_knownDialogues.Add(DialogueKey(dialogue.entries))) continue;

            PlaceRestored(Instantiate(_space, _journalContent));
            foreach (var entry in dialogue.entries)
            {
                PlaceRestored(CreatePhrase(entry.name, entry.text));
            }
            PlaceRestored(Instantiate(_space, _journalContent));
        }
    }

    private void PlaceRestored(GameObject item)
    {
        item.transform.SetSiblingIndex(_restoredSiblingIndex++);
    }

    private GameObject CreatePhrase(string phraseName, string text)
    {
        JournalSimplePhrase phrase = Instantiate(_simplePhrase, _journalContent).GetComponent<JournalSimplePhrase>();
        phrase.Name.text = phraseName;
        phrase.Text.text = text;
        return phrase.gameObject;
    }

    private void SaveSimplePhrase(DialogueBaseClass phraseData)
    {
        string phraseName = phraseData.simplePhrase.InputName ?? "";
        string text = phraseData.simplePhrase.InputText ?? "";

        _currentObjects.Add(CreatePhrase(phraseName, text));
        if (_currentEntries.Count < MaxEntriesPerDialogue)
        {
            _currentEntries.Add(new JournalEntry { name = Truncate(phraseName, MaxNameLength), text = Truncate(text, MaxTextLength) });
        }
    }

    private void CreateSpace(object sender, EventArgs e)
    {
        _currentObjects.Add(Instantiate(_space, _journalContent));
    }

    private void FinishDialogue()
    {
        if (_currentEntries.Count > 0)
        {
            if (_knownDialogues.Add(DialogueKey(_currentEntries)))
            {
                OnDialogueRecorded?.Invoke(_currentEntries.ToArray());
            }
            else
            {
                // такой разговор уже есть в журнале — повтор убираем
                foreach (var item in _currentObjects)
                {
                    Destroy(item);
                }
            }
        }
        _currentObjects.Clear();
        _currentEntries.Clear();
    }

    private static string DialogueKey(IEnumerable<JournalEntry> entries)
    {
        return string.Join("\u0001", entries.Select(e => (e.name ?? "") + "\u0002" + (e.text ?? "")));
    }

    private static string Truncate(string value, int maxLength)
    {
        return value.Length <= maxLength ? value : value.Substring(0, maxLength);
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
