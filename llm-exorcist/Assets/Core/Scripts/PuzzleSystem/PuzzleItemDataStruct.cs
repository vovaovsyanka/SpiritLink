using System;
using UnityEngine;

namespace Assets.Core.Scripts.PuzzleSystem
{
    [Serializable]
    public struct PuzzleItemDataStruct
    {
        public bool isActive;
        public int indexInSequence;
        public string puzzleText;
        public string puzzleShortText;
        [Multiline(4)] public string puzzleInfo;
    }
}
