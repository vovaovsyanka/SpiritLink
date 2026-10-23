using System;
using System.Collections;
using System.Collections.Generic;
using Assets.Core.Scripts.PuzzleSystem;
using Core.Scripts.PuzzleSystem;
using Core.Scripts.UI;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace Core.Scripts.Network
{
    /// <summary>
    /// Связывает сцену уровня с прогрессом на сервере. Создаётся сам (ApiClient) при загрузке LVL1–3.
    ///
    /// При входе: /passes/{id}/start, затем восстановление по фазе — найденные карточки снова
    /// в паззле, а при free_prompt дверь паззла сразу открыта. Незаконченный этап начинается заново.
    /// Во время игры: найденная карточка → /clues, прочитанный разговор → /journal (журнал
    /// восстанавливается при входе), первое открытие паззла → фаза puzzle, собранный паззл → free_prompt.
    /// done ставит сервер, когда игрок ввёл слово.
    /// </summary>
    public class LevelProgressController : MonoBehaviour
    {
        private static readonly Dictionary<string, string> SceneToPass = new()
        {
            { SceneInfo.LVL1_SCENE, "tony_stark" },
            { SceneInfo.LVL2_SCENE, "subnautica" },
            { SceneInfo.LVL3_SCENE, "cyberpunk" },
        };

        private static readonly string[] PhaseOrder =
            { Phases.Investigation, Phases.Puzzle, Phases.FreePrompt, Phases.Done };

        private string _passId;
        private string _phase = "";
        private bool _started;
        private readonly List<string> _pendingClues = new();
        private readonly List<JournalEntry[]> _pendingJournal = new();
        private readonly Dictionary<string, PuzzleItemDataStruct> _cardsByText = new();
        private PuzzleGameManager _puzzle;
        private PuzzleDoor _puzzleDoor;
        private Journal _journal;

        public static void AttachIfLevel(Scene scene)
        {
            if (!SceneToPass.TryGetValue(scene.name, out var passId)) return;

            var go = new GameObject("LevelProgress");
            SceneManager.MoveGameObjectToScene(go, scene);
            go.AddComponent<LevelProgressController>()._passId = passId;
        }

        private void OnEnable()
        {
            DialogueViewer.OnDialogueEnded += OnClueFound;
            PuzzleGameManager.OnSolved += OnPuzzleSolved;
            Journal.OnDialogueRecorded += OnJournalDialogue;
        }

        private void OnDisable()
        {
            DialogueViewer.OnDialogueEnded -= OnClueFound;
            PuzzleGameManager.OnSolved -= OnPuzzleSolved;
            Journal.OnDialogueRecorded -= OnJournalDialogue;
            if (_puzzleDoor != null) _puzzleDoor.OnPuzzleStart -= OnPuzzleOpened;
        }

        private IEnumerator Start()
        {
            _puzzle = FindAnyObjectByType<PuzzleGameManager>(FindObjectsInactive.Include);
            _puzzleDoor = FindAnyObjectByType<PuzzleDoor>(FindObjectsInactive.Include);
            _journal = FindAnyObjectByType<Journal>(FindObjectsInactive.Include);
            if (_puzzleDoor != null) _puzzleDoor.OnPuzzleStart += OnPuzzleOpened;
            CollectCards();

            yield return new WaitUntil(() => ApiClient.Instance != null && ApiClient.Instance.IsLoggedIn);

            ApiResult<PassState> result = null;
            yield return ApiClient.Instance.StartPass(_passId, r => result = r);
            if (!result.Ok)
            {
                RuntimeUi.Toast($"Прогресс уровня не сохраняется: {result.Error}");
                yield break;
            }

            _started = true;
            _phase = result.Data.phase;
            int clueCount = result.Data.collected_clues?.Length ?? 0;
            int restored = Restore(result.Data);
            if (_journal != null) _journal.RestoreSaved(result.Data.journal);
            Debug.Log($"LevelProgress: {_passId}, фаза {_phase}, карточек на сервере {clueCount}, " +
                      $"восстановлено {restored}, всего карточек в сцене {_cardsByText.Count}");

            foreach (var clue in _pendingClues)
            {
                SendClue(clue);
            }
            _pendingClues.Clear();

            foreach (var dialogue in _pendingJournal)
            {
                SendJournalDialogue(dialogue);
            }
            _pendingJournal.Clear();
        }

        /// <summary>Все карточки уровня из диалогов сцены: по тексту восстанавливаем найденные.</summary>
        private void CollectCards()
        {
            foreach (var viewer in FindObjectsByType<DialogueViewer>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            {
                if (viewer.Bunch == null || viewer.Bunch.PuzzleItemDatas == null) continue;
                foreach (var data in viewer.Bunch.PuzzleItemDatas)
                {
                    string key = ClueKey(data);
                    if (!string.IsNullOrEmpty(key) && !_cardsByText.ContainsKey(key))
                    {
                        _cardsByText.Add(key, data);
                    }
                }
            }
        }

        /// <summary>Возвращает число восстановленных карточек.</summary>
        private int Restore(PassState state)
        {
            int restored = 0;
            if (_puzzle != null && state.collected_clues != null)
            {
                foreach (var clue in state.collected_clues)
                {
                    if (_cardsByText.TryGetValue(clue, out var data))
                    {
                        _puzzle.RestorePuzzle(data);
                        restored++;
                    }
                    else
                    {
                        Debug.LogWarning($"LevelProgress: карточка «{clue}» не найдена в сцене (текст изменили?)");
                    }
                }
            }

            if (_phase == Phases.FreePrompt)
            {
                // паззл уже собран — сразу в свободный промпт
                if (_puzzle != null) _puzzle.MarkSolved();
                if (_puzzleDoor != null) _puzzleDoor.OpenInstantly();
            }
            return restored;
        }

        private void OnClueFound(PuzzleItemDataStruct data)
        {
            string clue = ClueKey(data);
            if (string.IsNullOrEmpty(clue)) return;

            if (!_started)
            {
                if (!_pendingClues.Contains(clue)) _pendingClues.Add(clue);
                return;
            }
            SendClue(clue);
        }

        private void SendClue(string clue)
        {
            if (_phase != Phases.Investigation && _phase != Phases.Puzzle) return;

            ApiClient.Instance.AddClue(_passId, clue, r =>
            {
                if (!r.Ok && r.StatusCode != 409 && r.StatusCode != 401)
                {
                    RuntimeUi.Toast($"Подсказка не сохранена: {r.Error}");
                }
            });
        }

        private void OnJournalDialogue(JournalEntry[] entries)
        {
            if (!_started)
            {
                _pendingJournal.Add(entries);
                return;
            }
            SendJournalDialogue(entries);
        }

        private void SendJournalDialogue(JournalEntry[] entries)
        {
            ApiClient.Instance.AddJournalDialogue(_passId, entries, r =>
            {
                if (!r.Ok && r.StatusCode != 409 && r.StatusCode != 401)
                {
                    RuntimeUi.Toast($"Журнал не сохранён: {r.Error}");
                }
            });
        }

        private void OnPuzzleOpened()
        {
            if (_started && _phase == Phases.Investigation)
            {
                SendPhase(Phases.Puzzle);
            }
        }

        private void OnPuzzleSolved()
        {
            if (_started && (_phase == Phases.Investigation || _phase == Phases.Puzzle))
            {
                SendPhase(Phases.FreePrompt);
            }
        }

        private void SendPhase(string phase)
        {
            AdvancePhase(phase);  // локально сразу, чтобы повторные события не слали лишнего
            ApiClient.Instance.SetPhase(_passId, phase, r =>
            {
                if (r.Ok)
                {
                    if (this != null) AdvancePhase(r.Data.phase);
                }
                else if (r.StatusCode != 409 && r.StatusCode != 401)
                {
                    RuntimeUi.Toast($"Прогресс не сохранён: {r.Error}");
                }
            });
        }

        /// <summary>Фаза только растёт: ответы на параллельные запросы могут прийти не по порядку.</summary>
        private void AdvancePhase(string phase)
        {
            if (Array.IndexOf(PhaseOrder, phase) > Array.IndexOf(PhaseOrder, _phase))
            {
                _phase = phase;
            }
        }

        private static string ClueKey(PuzzleItemDataStruct data)
        {
            // сервер обрезает пробелы по краям — ключ должен совпадать
            return string.IsNullOrEmpty(data.puzzleText) ? "" : data.puzzleText.Trim();
        }
    }
}
