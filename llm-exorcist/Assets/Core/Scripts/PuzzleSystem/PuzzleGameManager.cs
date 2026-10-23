using Assets.Core.Scripts.PuzzleSystem;
using DG.Tweening;
using System.Collections.Generic;
using UnityEngine;

namespace Core.Scripts.PuzzleSystem
{
    /// <summary>
    /// Управляет пазлом: создаёт блоки по окончании диалогов, ведёт перетаскивание,
    /// проверяет собранную последовательность и открывает дверь.
    /// </summary>
    public class PuzzleGameManager : MonoBehaviour
    {
        private const string WorkspaceTag = "CodeSpace";
        private const string BlocksTag = "BlocksSpace";
        private const float ReturnDuration = 0.3f;

        [SerializeField] private GameObject _puzzleCanvas;
        [SerializeField] private Transform _spawnerSpaceTransform;
        [SerializeField] private GameObject _containerPrefab;
        [SerializeField] private GameObject _spawnerPrefab;
        [Tooltip("Правильные последовательности: индексы блоков подряд, например 2135, либо через разделитель: 2-1-3-5")]
        [SerializeField] private string[] _puzzleOrders;
        [Space(10)]
        [SerializeField] private PuzzleDoor _puzzleDoor;

        /// <summary>Паззл собран правильно (для сохранения прогресса).</summary>
        public static event System.Action OnSolved;

        private RectTransform _workspaceTransform;
        private RectTransform _blocksTransform;
        private Camera _uiCamera;

        private readonly List<int[]> _solutions = new();
        private readonly HashSet<string> _createdPuzzleKeys = new();
        private bool _isSolved;
        private int _testPuzzleCounter;

        // состояние текущего перетаскивания
        private PuzzleContainer _dragContainer;
        private PuzzleItem _dragTarget;
        private Vector2 _dragOffset;

        private void Awake()
        {
            if (_puzzleCanvas == null)
            {
                Debug.LogError("PuzzleGameManager: не задан _puzzleCanvas", this);
                enabled = false;
                return;
            }

            // ищем среди всех детей канваса, включая неактивные
            foreach (var child in _puzzleCanvas.GetComponentsInChildren<RectTransform>(true))
            {
                if (_workspaceTransform == null && child.CompareTag(WorkspaceTag)) _workspaceTransform = child;
                if (_blocksTransform == null && child.CompareTag(BlocksTag)) _blocksTransform = child;
            }

            if (_workspaceTransform == null || _blocksTransform == null)
            {
                Debug.LogError($"PuzzleGameManager: не найдены объекты с тегами {WorkspaceTag}/{BlocksTag}", this);
                enabled = false;
                return;
            }

            var canvas = _puzzleCanvas.GetComponent<Canvas>();
            if (canvas != null && canvas.renderMode != RenderMode.ScreenSpaceOverlay)
            {
                _uiCamera = canvas.worldCamera;
            }

            ParseSolutions();
        }

        private void Start()
        {
            EndPuzzle();
        }

        private void OnEnable()
        {
            if (_puzzleDoor != null)
            {
                _puzzleDoor.OnPuzzleStart += StartPuzzle;
                _puzzleDoor.OnPuzzleEnd += EndPuzzle;
            }
            DialogueViewer.OnDialogueEnded += CreatePuzzle;
        }

        private void OnDisable()
        {
            if (_puzzleDoor != null)
            {
                _puzzleDoor.OnPuzzleStart -= StartPuzzle;
                _puzzleDoor.OnPuzzleEnd -= EndPuzzle;
            }
            DialogueViewer.OnDialogueEnded -= CreatePuzzle;
        }

        // ── Показ / скрытие ──────────────────────────────────────────────────

        private void StartPuzzle()
        {
            _puzzleCanvas.SetActive(true);
        }

        private void EndPuzzle()
        {
            CancelDrag();
            _puzzleCanvas.SetActive(false);
        }

        // ── Создание блоков ──────────────────────────────────────────────────

        private void CreatePuzzle(PuzzleItemDataStruct data)
        {
            // диалог можно пройти повторно — второй раз тот же блок не создаём
            string key = $"{data.indexInSequence}|{data.puzzleText}|{data.puzzleShortText}";
            if (!_createdPuzzleKeys.Add(key)) return;

            var spawner = Instantiate(_spawnerPrefab, _spawnerSpaceTransform).GetComponent<PuzzleSpawner>();
            spawner.Initialize(this, data);
        }

        /// <summary>Возвращает карточку, найденную в прошлый заход (прогресс с сервера).</summary>
        public void RestorePuzzle(PuzzleItemDataStruct data)
        {
            CreatePuzzle(data);
        }

        /// <summary>Паззл уже собран в прошлый заход — повторно не проверяем.</summary>
        public void MarkSolved()
        {
            _isSolved = true;
        }

        [ContextMenu("Spawn Test Puzzle")]
        private void SpawnTestPuzzle()
        {
            _testPuzzleCounter++;
            CreatePuzzle(new PuzzleItemDataStruct
            {
                isActive = true,
                indexInSequence = _testPuzzleCounter,
                puzzleText = $"Тестовый блок {_testPuzzleCounter}",
                puzzleShortText = $"Блок {_testPuzzleCounter}",
                puzzleInfo = "Блок для проверки перетаскивания"
            });
        }

        public PuzzleContainer InstantiateContainer(IEnumerable<PuzzleItem> puzzles, Vector3 position, Transform parent = null)
        {
            var container = Instantiate(_containerPrefab, parent != null ? parent : _puzzleCanvas.transform)
                .GetComponent<PuzzleContainer>();
            container.transform.position = position;
            container.Insert(puzzles, 0);
            return container;
        }

        // ── Перетаскивание ───────────────────────────────────────────────────

        /// <summary>Начинает перетаскивание блока вместе со всеми блоками под ним.</summary>
        public bool BeginDrag(PuzzleItem item, Vector2 pointer)
        {
            var source = item.ParentContainer;
            if (source == null) return false;

            int index = source.IndexOf(item);
            if (index < 0) return false;

            CancelDrag();

            PuzzleContainer dragged;
            if (index > 0)
            {
                // хвост цепочки отделяется в новый контейнер, который остаётся ровно там, где был
                Vector2 topBefore = item.GetTopPoint();
                var tail = source.TakeFrom(index);
                dragged = InstantiateContainer(tail, source.transform.position, _puzzleCanvas.transform);
                dragged.RebuildLayout();
                dragged.transform.position += (Vector3)(topBefore - item.GetTopPoint());
                source.RebuildLayout();
            }
            else
            {
                dragged = source;
                dragged.transform.SetParent(_puzzleCanvas.transform, true);
            }

            dragged.transform.SetAsLastSibling();
            _dragContainer = dragged;
            _dragTarget = null;
            _dragOffset = (Vector2)dragged.transform.position - pointer;
            return true;
        }

        public void Drag(Vector2 pointer)
        {
            if (_dragContainer == null) return;

            _dragContainer.transform.position = pointer + _dragOffset;
            UpdateConnectionTarget();
        }

        public void EndDrag(Vector2 pointer)
        {
            var dragged = _dragContainer;
            var target = _dragTarget;
            _dragContainer = null;
            _dragTarget = null;

            if (dragged == null) return;

            var targetContainer = target != null ? target.ParentContainer : null;
            if (targetContainer != null && targetContainer != dragged)
            {
                targetContainer.HideFreeSpace();
                int insertIndex = targetContainer.IndexOf(target) + 1;
                targetContainer.Insert(dragged.TakeAll(), insertIndex);
                Destroy(dragged.gameObject);
                CheckSolution(targetContainer);
                return;
            }

            if (target != null && target.ParentContainer != null)
            {
                target.ParentContainer.HideFreeSpace();
            }

            if (IsOnWorkspace(pointer))
            {
                dragged.transform.SetParent(_workspaceTransform, true);
            }
            else
            {
                ReturnToSpawners(dragged, false);
            }
        }

        /// <summary>Прерывает перетаскивание (например, игрок отошёл от двери) и возвращает блоки на место.</summary>
        private void CancelDrag()
        {
            if (_dragContainer == null) return;

            if (_dragTarget != null && _dragTarget.ParentContainer != null)
            {
                _dragTarget.ParentContainer.HideFreeSpace();
            }

            var dragged = _dragContainer;
            _dragContainer = null;
            _dragTarget = null;
            ReturnToSpawners(dragged, true);
        }

        private void UpdateConnectionTarget()
        {
            var first = _dragContainer.First;
            var best = first != null ? FindConnectionTarget(first.GetTopPoint()) : null;
            if (best == _dragTarget) return;

            if (_dragTarget != null && _dragTarget.ParentContainer != null)
            {
                _dragTarget.ParentContainer.HideFreeSpace();
            }

            _dragTarget = best;
            if (best != null)
            {
                best.ParentContainer.ShowFreeSpace(best, _dragContainer.GetContentSize());
            }
        }

        /// <summary>Блок на рабочей области, в зону соединения которого попала точка. Из нескольких — ближайший.</summary>
        private PuzzleItem FindConnectionTarget(Vector2 point)
        {
            PuzzleItem best = null;
            float bestDistance = float.MaxValue;

            foreach (Transform child in _workspaceTransform)
            {
                if (!child.TryGetComponent(out PuzzleContainer container) || container == _dragContainer) continue;

                foreach (var candidate in container.Puzzles)
                {
                    var area = candidate.ConnectionArea;
                    if (!RectTransformUtility.RectangleContainsScreenPoint(area, point, _uiCamera)) continue;

                    float distance = Vector2.Distance(area.TransformPoint(area.rect.center), point);
                    if (distance < bestDistance)
                    {
                        bestDistance = distance;
                        best = candidate;
                    }
                }
            }
            return best;
        }

        private bool IsOnWorkspace(Vector2 point)
        {
            return RectTransformUtility.RectangleContainsScreenPoint(_workspaceTransform, point, _uiCamera)
                && !RectTransformUtility.RectangleContainsScreenPoint(_blocksTransform, point, _uiCamera);
        }

        // ── Возврат в панель блоков ──────────────────────────────────────────

        private void ReturnToSpawners(PuzzleContainer container, bool instant)
        {
            foreach (var puzzle in container.TakeAll())
            {
                ReturnToSpawner(puzzle, instant);
            }
            Destroy(container.gameObject);
        }

        private void ReturnToSpawner(PuzzleItem puzzle, bool instant)
        {
            var spawner = puzzle.Spawner;
            if (spawner == null)
            {
                Destroy(puzzle.gameObject);
                return;
            }

            // блок уже не числится ни в одном контейнере, пока летит обратно
            puzzle.transform.SetParent(_puzzleCanvas.transform, true);

            if (instant)
            {
                spawner.Restore(puzzle);
                return;
            }

            puzzle.transform.DOMove(spawner.transform.position, ReturnDuration)
                .SetEase(Ease.InOutSine)
                .SetLink(puzzle.gameObject)
                .OnComplete(() =>
                {
                    if (spawner != null && puzzle != null)
                    {
                        spawner.Restore(puzzle);
                    }
                });
        }

        // ── Проверка решения ─────────────────────────────────────────────────

        private void ParseSolutions()
        {
            _solutions.Clear();
            if (_puzzleOrders == null) return;

            foreach (var order in _puzzleOrders)
            {
                if (string.IsNullOrWhiteSpace(order)) continue;

                var indices = new List<int>();
                bool hasSeparator = false;
                foreach (char c in order)
                {
                    if (!char.IsDigit(c)) hasSeparator = true;
                }

                if (hasSeparator)
                {
                    foreach (var part in order.Split(new[] { '-', ',', ' ', ';', '.' }, System.StringSplitOptions.RemoveEmptyEntries))
                    {
                        if (int.TryParse(part, out int value)) indices.Add(value);
                    }
                }
                else
                {
                    foreach (char c in order) indices.Add(c - '0');
                }

                if (indices.Count > 0) _solutions.Add(indices.ToArray());
            }
        }

        private void CheckSolution(PuzzleContainer container)
        {
            if (_isSolved || container == null) return;

            var puzzles = container.Puzzles;
            foreach (var solution in _solutions)
            {
                if (puzzles.Count != solution.Length) continue;

                bool correct = true;
                for (int i = 0; i < solution.Length; i++)
                {
                    if (!puzzles[i].IsActive || puzzles[i].OrderInSequence != solution[i])
                    {
                        correct = false;
                        break;
                    }
                }

                if (correct)
                {
                    _isSolved = true;
                    OnSolved?.Invoke();
                    if (_puzzleDoor != null) _puzzleDoor.OpenDoor();
                    return;
                }
            }
        }
    }
}
