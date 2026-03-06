import { buildAudioFormData } from './useAudioRecording';

// Mock expo-file-system/next File class
const mockBlob = new Blob(['test'], { type: 'audio/mp4' });
const mockBlobFn = jest.fn().mockReturnValue(mockBlob);

jest.mock('expo-file-system/next', () => ({
  File: jest.fn().mockImplementation((uri: string) => ({
    blob: mockBlobFn,
    name: uri.split('/').pop() ?? 'audio.m4a',
  })),
}));

describe('buildAudioFormData', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it('creates a FormData with an audio field', () => {
    const formData = buildAudioFormData('file:///path/to/audio.m4a');

    expect(formData).toBeInstanceOf(FormData);
  });

  it('creates an ExpoFile from the given URI', () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { File: MockFile } = require('expo-file-system/next');

    buildAudioFormData('file:///recordings/test.m4a');

    expect(MockFile).toHaveBeenCalledWith('file:///recordings/test.m4a');
  });

  it('appends the blob with the file name', () => {
    const appendSpy = jest.spyOn(FormData.prototype, 'append');

    buildAudioFormData('file:///recordings/test.m4a');

    expect(appendSpy).toHaveBeenCalledWith(
      'audio',
      mockBlob,
      'test.m4a',
    );

    appendSpy.mockRestore();
  });

  it('handles different URI formats without error', () => {
    expect(() => buildAudioFormData('file:///a.m4a')).not.toThrow();
    expect(() =>
      buildAudioFormData('file:///long/path/to/recording.m4a'),
    ).not.toThrow();
  });
});
